from b_asic.scheduler import ListScheduler


class EarliestDeadlineScheduler(ListScheduler):
    """Scheduler that implements the earliest-deadline-first algorithm."""

    @property
    def sort_indices(self) -> tuple[tuple[int, bool]]:
        return ((1, True),)


class LeastSlackTimeScheduler(ListScheduler):
    """Scheduler that implements the least slack time first algorithm."""

    @property
    def sort_indices(self) -> tuple[tuple[int, bool]]:
        return ((2, True),)


class MaxFanOutScheduler(ListScheduler):
    """Scheduler that implements the maximum fan-out algorithm."""

    @property
    def sort_indices(self) -> tuple[tuple[int, bool]]:
        return ((3, False),)


class HybridScheduler(ListScheduler):
    """Scheduler that implements a hybrid algorithm. Will receive a new name once finalized."""

    @property
    def sort_indices(self) -> tuple[tuple[int, bool]]:
        return ((2, True), (3, False))
