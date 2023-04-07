from qtpy.QtCore import QObject, Signal

from b_asic.signal_flow_graph import SFG
from b_asic.simulation import Simulation


class SimulationWorker(QObject):
    finished = Signal(Simulation)

    def __init__(self, sfg: SFG, properties):
        super().__init__()
        self._sfg = sfg
        self._props = properties

    def start_simulation(self):
        simulation = Simulation(self._sfg, input_providers=self._props["input_values"])
        simulation.run_for(
            self._props["iteration_count"],
            save_results=self._props["all_results"],
        )
        self.finished.emit(simulation)
