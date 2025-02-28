from b_asic.scheduler import ListScheduler
from b_asic.types import GraphID, TypeName


class EarliestDeadlineScheduler(ListScheduler):
    """Scheduler that implements the earliest-deadline-first algorithm."""

    def __init__(
        self,
        max_resources: dict[TypeName, int] | None = None,
        max_concurrent_reads: int | None = None,
        max_concurrent_writes: int | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        cyclic: bool | None = False,
    ) -> None:
        super().__init__(
            max_resources=max_resources,
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            input_times=input_times,
            output_delta_times=output_delta_times,
            sort_order=((1, True),),
        )


class LeastSlackTimeScheduler(ListScheduler):
    """Scheduler that implements the least slack time first algorithm."""

    def __init__(
        self,
        max_resources: dict[TypeName, int] = None,
        max_concurrent_reads: int = None,
        max_concurrent_writes: int = None,
        input_times: dict["GraphID", int] = None,
        output_delta_times: dict["GraphID", int] = None,
    ) -> None:
        super().__init__(
            max_resources=max_resources,
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            input_times=input_times,
            output_delta_times=output_delta_times,
            sort_order=((2, True),),
        )


class MaxFanOutScheduler(ListScheduler):
    """Scheduler that implements the maximum fan-out algorithm."""

    def __init__(
        self,
        max_resources: dict[TypeName, int] = None,
        max_concurrent_reads: int = None,
        max_concurrent_writes: int = None,
        input_times: dict["GraphID", int] = None,
        output_delta_times: dict["GraphID", int] = None,
    ) -> None:
        super().__init__(
            max_resources=max_resources,
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            input_times=input_times,
            output_delta_times=output_delta_times,
            sort_order=((3, False),),
        )


class HybridScheduler(ListScheduler):
    """Scheduler that implements a hybrid algorithm. Will receive a new name once finalized."""

    def __init__(
        self,
        max_resources: dict[TypeName, int] = None,
        max_concurrent_reads: int = None,
        max_concurrent_writes: int = None,
        input_times: dict["GraphID", int] = None,
        output_delta_times: dict["GraphID", int] = None,
    ) -> None:
        super().__init__(
            max_resources=max_resources,
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            input_times=input_times,
            output_delta_times=output_delta_times,
            sort_order=((2, True), (3, False)),
        )
