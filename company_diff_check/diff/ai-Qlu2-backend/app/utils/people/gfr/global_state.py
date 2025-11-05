running_tasks = {}


def register_task(task_id, task):
    """Register a new task by ID."""
    running_tasks[task_id] = task


def deregister_task(task_id):
    """Remove a task from the registry by ID."""
    running_tasks.pop(task_id, None)


def is_task_running(task_id):
    """Check if a task is currently running by ID."""
    return task_id in running_tasks
