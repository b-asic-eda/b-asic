"""
B-ASIC GUI Simulation Worker Module.

Contains a class for simulation workers.
"""

from qtpy.QtCore import QObject, Signal

from b_asic.signal_flow_graph import SFG
from b_asic.simulation import Simulation


class SimulationWorker(QObject):
    """
    Simulation worker to enable running simulation in a separate thread.

    Parameters
    ----------
    sfg : SFG
        The signal flow graph to simulate.
    properties : dict
        Dictionary containing information about the simulation.
    """

    finished = Signal(Simulation)

    def __init__(self, sfg: SFG, properties) -> None:
        super().__init__()
        self._sfg = sfg
        self._props = properties

    def start_simulation(self) -> None:
        """Start simulation and emit signal when finished."""
        simulation = Simulation(self._sfg, input_providers=self._props["input_values"])
        simulation.run_for(
            self._props["iteration_count"],
            save_results=self._props["all_results"],
        )
        self.finished.emit(simulation)
