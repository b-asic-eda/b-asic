from typing import Dict, Int, List

from b_asic.operation import AbstractOperation
from b_asic.port import InputPort, OutputPort


class Process:
    def __init__(self, start_time : Int, execution_time : Int):
        self._start_time = start_time
        self._execution_time = execution_time

    def __lt__(self, other):
        return self._start_time < other.start_time or (
                    self._start_time == other.start_time and self.execution_time > _execution_time)

    @property
    def start_time(self) -> Int:
        return self._start_time

    @property
    def execution_time(self) -> Int:
        return self._execution_time


class OperatorProcess(Process):
    def __init__(self, start_time : Int, operation : AbstractOperation):
        super().__init__(start_time, operation.execution_time)
        self._operation = operation


class MemoryVariable(Process):
    def __init__(self, write_time : Int, write_port : OutputPort, reads : Dict[InputPort, Int]):
        self._read_ports, self._life_times = reads.values()
        super().__init__(start_time=write_time, execution_time=max(self._life_times))

    @property
    def life_times(self) -> List[Int]:
        return self._life_times

    @property
    def read_ports(self) -> List[InputPort]:
        return self._read_ports
