import json
import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict


class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    PROCESSING = "processing"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = None

    def update(
            self,
            status: Optional[TaskStatus] = None,
            progress: Optional[float] = None,
            message: Optional[str] = None
    ):

        if status is not None:
            self.status = status

        if progress is not None:
            self.progress = progress

        if message is not None:
            self.message = message

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'status': self.status.value,
            'progress': self.progress,
            'message': self.message
        }

    def to_json(self):
        return json.dumps(self.to_dict())


# TODO: Is a singleton actually a good idea? Hundreds of uploads could occur at the same time
class TaskManager:
    _instance = None
    _lock = threading.Lock()

    # Creates a singleton. Ensuring a single instance only gets create across the app
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)

                    cls._instance._tasks: Dict[str, TaskInfo] = {}

        return cls._instance

    def create_task(self):
        with self._lock:
            task_id = str(uuid.uuid4()).replace('-', '').upper()
            task_info = TaskInfo(task_id=task_id)

            self._tasks[task_id] = task_info

            return task_id

    def update_task(
            self,
            task_id: str,
            status: Optional[TaskStatus] = None,
            progress: Optional[float] = None,
            message: Optional[str] = None
    ):
        with self._lock:
            if task_id not in self._tasks:
                KeyError(f"Task {task_id} not found")

            task = self._tasks[task_id]
            task.update(status=status, progress=progress, message=message)

    def get_task(self, task_id: str):
        with self._lock:
            return self._tasks.get(task_id)


task_manager = TaskManager()
