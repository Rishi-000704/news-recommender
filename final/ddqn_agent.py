from __future__ import annotations

import json
import queue
import random
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.optim import Adam

from database import DB_PATH, db_connect, fetch_categories, init_db


MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True)


class DuelingDQN(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.features = nn.Sequential(nn.Linear(state_dim, 128), nn.ReLU())
        self.value = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))
        self.advantage = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, action_dim))

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        x = self.features(state)
        value = self.value(x)
        advantage = self.advantage(x)
        return value + (advantage - advantage.mean(dim=1, keepdim=True))


@dataclass
class Transition:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.buffer: deque[Transition] = deque(maxlen=capacity)

    def push(self, transition: Transition) -> None:
        self.buffer.append(transition)

    def sample(self, batch_size: int) -> list[Transition]:
        return random.sample(self.buffer, batch_size)

    def __len__(self) -> int:
        return len(self.buffer)


class DDQNAgent:
    def __init__(
        self,
        categories: Sequence[str] | None = None,
        user_id: str = "default",
        gamma: float = 0.9,
        lr: float = 1e-3,
        batch_size: int = 16,
        target_update: int = 20,
        save_interval: int = 20,
        db_path: Path = DB_PATH,
    ):
        init_db(db_path)
        self.db_path = db_path
        self.user_id = user_id
        self.categories = list(categories or fetch_categories(db_path))
        if not self.categories:
            self.categories = ["general"]
        self.action_dim = len(self.categories)
        self.gamma = gamma
        self.batch_size = batch_size
        self.target_update = target_update
        self.save_interval = save_interval
        self.device = torch.device("cpu")
        self.model = DuelingDQN(5, self.action_dim).to(self.device)
        self.target_model = DuelingDQN(5, self.action_dim).to(self.device)
        self.optimizer = Adam(self.model.parameters(), lr=lr)
        self.replay = ReplayBuffer(500)
        self.step = 0
        self.epsilon = 0.15
        self._save_queue: queue.Queue[dict[str, object]] = queue.Queue(maxsize=1)
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self._save_thread.start()
        self._load_or_init()

    @property
    def model_path(self) -> Path:
        safe_user = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.user_id)
        return MODEL_DIR / f"ddqn_{safe_user}.pt"

    def _load_or_init(self) -> None:
        with db_connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT step, epsilon, category_order FROM agent_state WHERE user_id = ?",
                (self.user_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT OR REPLACE INTO agent_state(user_id, category_order) VALUES (?, ?)",
                    (self.user_id, json.dumps(self.categories)),
                )
            else:
                self.step = int(row["step"])
                self.epsilon = float(row["epsilon"])

        if self.model_path.exists():
            payload = torch.load(self.model_path, map_location=self.device, weights_only=False)
            saved_categories = payload.get("categories", self.categories)
            if list(saved_categories) == self.categories:
                self.model.load_state_dict(payload["model"])
                self.target_model.load_state_dict(payload["target_model"])
                self.optimizer.load_state_dict(payload["optimizer"])
                self.step = int(payload.get("step", self.step))
                self.epsilon = float(payload.get("epsilon", self.epsilon))
            else:
                self.target_model.load_state_dict(self.model.state_dict())
        else:
            self.target_model.load_state_dict(self.model.state_dict())

    def _do_save(self, payload: dict[str, object]) -> None:
        torch.save(
            {
                "model": payload["model"],
                "target_model": payload["target_model"],
                "optimizer": payload["optimizer"],
                "categories": payload["categories"],
                "step": payload["step"],
                "epsilon": payload["epsilon"],
            },
            self.model_path,
        )
        with db_connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_state(user_id, step, epsilon, category_order, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.user_id, payload["step"], payload["epsilon"], json.dumps(payload["categories"])),
            )

    def save(self) -> None:
        payload = {
            "model": self.model.state_dict(),
            "target_model": self.target_model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "categories": self.categories,
            "step": self.step,
            "epsilon": self.epsilon,
        }
        self._enqueue_save(payload)

    def _enqueue_save(self, payload: dict[str, object]) -> None:
        try:
            if self._save_queue.full():
                _ = self._save_queue.get_nowait()
            self._save_queue.put_nowait(payload)
        except queue.Full:
            pass

    def _save_worker(self) -> None:
        while True:
            payload = self._save_queue.get()
            if payload is None:
                break
            try:
                self._do_save(payload)
            except Exception:
                pass
            finally:
                self._save_queue.task_done()

    def q_values(self, state: Sequence[float]) -> np.ndarray:
        with torch.no_grad():
            state_tensor = torch.tensor([state], dtype=torch.float32, device=self.device)
            return self.model(state_tensor).cpu().numpy()[0]

    def q_values_batch(self, states: Sequence[Sequence[float]]) -> np.ndarray:
        with torch.no_grad():
            state_tensor = torch.tensor(np.array(states, dtype=np.float32), device=self.device)
            return self.model(state_tensor).cpu().numpy()

    def choose_action(self, state: Sequence[float], blocked: set[str] | None = None) -> int:
        blocked = blocked or set()
        allowed = [i for i, cat in enumerate(self.categories) if cat not in blocked]
        if not allowed:
            allowed = list(range(self.action_dim))
        if random.random() < self.epsilon:
            return random.choice(allowed)
        q = self.q_values(state)
        masked = np.full_like(q, -1e9, dtype=np.float32)
        masked[allowed] = q[allowed]
        return int(masked.argmax())

    def train_step(self) -> float | None:
        if len(self.replay) < self.batch_size:
            return None

        batch = self.replay.sample(self.batch_size)
        states = torch.tensor(np.array([t.state for t in batch]), dtype=torch.float32)
        actions = torch.tensor([t.action for t in batch], dtype=torch.long).unsqueeze(1)
        rewards = torch.tensor([t.reward for t in batch], dtype=torch.float32).unsqueeze(1)
        next_states = torch.tensor(np.array([t.next_state for t in batch]), dtype=torch.float32)
        dones = torch.tensor([t.done for t in batch], dtype=torch.float32).unsqueeze(1)

        q_values = self.model(states).gather(1, actions)
        with torch.no_grad():
            next_actions = self.model(next_states).argmax(dim=1, keepdim=True)
            next_q = self.target_model(next_states).gather(1, next_actions)
            targets = rewards + self.gamma * next_q * (1.0 - dones)

        loss = nn.functional.mse_loss(q_values, targets)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        self.step += 1
        self.epsilon = max(0.03, self.epsilon * 0.995)
        if self.step % self.target_update == 0:
            self.target_model.load_state_dict(self.model.state_dict())
        return float(loss.item())

    def observe(
        self,
        state: Sequence[float],
        category: str,
        reward: float,
        next_state: Sequence[float],
        done: bool = False,
    ) -> float | None:
        if category not in self.categories:
            return None
        action = self.categories.index(category)
        self.replay.push(
            Transition(
                np.array(state, dtype=np.float32),
                action,
                float(reward),
                np.array(next_state, dtype=np.float32),
                done,
            )
        )
        loss = self.train_step()
        if self.step % self.save_interval == 0:
            self.save()
        return loss
