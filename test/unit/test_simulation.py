import numpy as np
import pytest

from b_asic.signal_generator import Impulse
from b_asic.simulation import Simulation


class TestRunFor:
    def test_with_lambdas_as_input(self, sfg_two_inputs_two_outputs):
        simulation = Simulation(
            sfg_two_inputs_two_outputs, [lambda n: n + 3, lambda n: 1 + n * 2]
        )

        output = simulation.run_for(101, save_results=True)

        assert output[0] == 304
        assert output[1] == 505

        assert simulation.results["0"][100] == 304
        assert simulation.results["1"][100] == 505

        assert simulation.results["in0"][0] == 3
        assert simulation.results["in1"][0] == 1
        assert simulation.results["add0"][0] == 4
        assert simulation.results["add1"][0] == 5
        assert simulation.results["0"][0] == 4
        assert simulation.results["1"][0] == 5

        assert simulation.results["in0"][1] == 4
        assert simulation.results["in1"][1] == 3
        assert simulation.results["add0"][1] == 7
        assert simulation.results["add1"][1] == 10
        assert simulation.results["0"][1] == 7
        assert simulation.results["1"][1] == 10

        assert simulation.results["in0"][2] == 5
        assert simulation.results["in1"][2] == 5
        assert simulation.results["add0"][2] == 10
        assert simulation.results["add1"][2] == 15
        assert simulation.results["0"][2] == 10
        assert simulation.results["1"][2] == 15

        assert simulation.results["in0"][3] == 6
        assert simulation.results["in1"][3] == 7
        assert simulation.results["add0"][3] == 13
        assert simulation.results["add1"][3] == 20
        assert simulation.results["0"][3] == 13
        assert simulation.results["1"][3] == 20

        assert simulation.iteration == 101

    def test_with_numpy_arrays_as_input(self, sfg_two_inputs_two_outputs):
        input0 = np.array([5, 9, 25, -5, 7])
        input1 = np.array([7, 3, 3, 54, 2])
        simulation = Simulation(sfg_two_inputs_two_outputs, [input0, input1])

        output = simulation.run_for(5, save_results=True)

        assert output[0] == 9
        assert output[1] == 11

        assert isinstance(simulation.results["in0"], np.ndarray)
        assert isinstance(simulation.results["in1"], np.ndarray)
        assert isinstance(simulation.results["add0"], np.ndarray)
        assert isinstance(simulation.results["add1"], np.ndarray)
        assert isinstance(simulation.results["0"], np.ndarray)
        assert isinstance(simulation.results["1"], np.ndarray)

        assert simulation.results["in0"][0] == 5
        assert simulation.results["in1"][0] == 7
        assert simulation.results["add0"][0] == 12
        assert simulation.results["add1"][0] == 19
        assert simulation.results["0"][0] == 12
        assert simulation.results["1"][0] == 19

        assert simulation.results["in0"][1] == 9
        assert simulation.results["in1"][1] == 3
        assert simulation.results["add0"][1] == 12
        assert simulation.results["add1"][1] == 15
        assert simulation.results["0"][1] == 12
        assert simulation.results["1"][1] == 15

        assert simulation.results["in0"][2] == 25
        assert simulation.results["in1"][2] == 3
        assert simulation.results["add0"][2] == 28
        assert simulation.results["add1"][2] == 31
        assert simulation.results["0"][2] == 28
        assert simulation.results["1"][2] == 31

        assert simulation.results["in0"][3] == -5
        assert simulation.results["in1"][3] == 54
        assert simulation.results["add0"][3] == 49
        assert simulation.results["add1"][3] == 103
        assert simulation.results["0"][3] == 49
        assert simulation.results["1"][3] == 103

        assert simulation.results["0"][4] == 9
        assert simulation.results["1"][4] == 11

    def test_with_numpy_array_overflow(self, sfg_two_inputs_two_outputs):
        input0 = np.array([5, 9, 25, -5, 7])
        input1 = np.array([7, 3, 3, 54, 2])
        simulation = Simulation(sfg_two_inputs_two_outputs, [input0, input1])
        simulation.run_for(5)
        with pytest.raises(IndexError):
            simulation.step()

    def test_run_whole_numpy_array(self, sfg_two_inputs_two_outputs):
        input0 = np.array([5, 9, 25, -5, 7])
        input1 = np.array([7, 3, 3, 54, 2])
        simulation = Simulation(sfg_two_inputs_two_outputs, [input0, input1])
        simulation.run()
        assert len(simulation.results["0"]) == 5
        assert len(simulation.results["1"]) == 5
        with pytest.raises(IndexError):
            simulation.step()

    def test_delay(self, sfg_delay):
        simulation = Simulation(sfg_delay)
        simulation.set_input(0, [5, -2, 25, -6, 7, 0])
        simulation.run_for(6, save_results=True)

        assert simulation.results["0"][0] == 0
        assert simulation.results["0"][1] == 5
        assert simulation.results["0"][2] == -2
        assert simulation.results["0"][3] == 25
        assert simulation.results["0"][4] == -6
        assert simulation.results["0"][5] == 7

    def test_delay_single_input_sequence(self, sfg_delay):
        simulation = Simulation(sfg_delay, [[5, -2, 25, -6, 7, 0]])
        simulation.run_for(6, save_results=True)

        assert simulation.results["0"][0] == 0
        assert simulation.results["0"][1] == 5
        assert simulation.results["0"][2] == -2
        assert simulation.results["0"][3] == 25
        assert simulation.results["0"][4] == -6
        assert simulation.results["0"][5] == 7

    def test_delay_single_input_generator(self, sfg_delay):
        simulation = Simulation(sfg_delay, [Impulse()])
        simulation.run_for(3, save_results=True)

        assert simulation.results["0"][0] == 0
        assert simulation.results["0"][1] == 1
        assert simulation.results["0"][2] == 0

    def test_two_inputs_single_array(self, sfg_two_inputs_two_outputs):
        input_data = [5, 7, 9]
        with pytest.raises(ValueError, match=r"Wrong number of inputs supplied"):
            Simulation(sfg_two_inputs_two_outputs, input_data)

    def test_find_result_key(self, precedence_sfg_delays):
        sim = Simulation(
            precedence_sfg_delays,
            [[0, 4, 542, 42, 31.314, 534.123, -453415, 5431]],
        )
        sim.run()
        assert (
            sim.results[precedence_sfg_delays.find_result_keys_by_name("ADD2")[0]][4]
            == 31220
        )
        assert (
            sim.results[precedence_sfg_delays.find_result_keys_by_name("A1")[0]][2]
            == 80
        )


class TestRun:
    def test_save_results(self, sfg_two_inputs_two_outputs):
        simulation = Simulation(sfg_two_inputs_two_outputs, [2, 3])
        assert not simulation.results
        simulation.run_for(10, save_results=False)
        assert not simulation.results
        simulation.run_for(10)
        assert len(simulation.results["0"]) == 10
        assert len(simulation.results["1"]) == 10
        simulation.run_for(10, save_results=True)
        assert len(simulation.results["0"]) == 20
        assert len(simulation.results["1"]) == 20
        simulation.run_for(10, save_results=False)
        assert len(simulation.results["0"]) == 20
        assert len(simulation.results["1"]) == 20
        simulation.run_for(13, save_results=True)
        assert len(simulation.results["0"]) == 33
        assert len(simulation.results["1"]) == 33
        simulation.step(save_results=False)
        assert len(simulation.results["0"]) == 33
        assert len(simulation.results["1"]) == 33
        simulation.step()
        assert len(simulation.results["0"]) == 34
        assert len(simulation.results["1"]) == 34
        simulation.clear_results()
        assert not simulation.results

    def test_nested(self, sfg_nested):
        input0 = np.array([5, 9])
        input1 = np.array([7, 3])
        simulation = Simulation(sfg_nested, [input0, input1])

        output0 = simulation.step()
        output1 = simulation.step()

        assert output0[0] == 11405
        assert output1[0] == 4221

    def test_accumulator(self, sfg_accumulator):
        data_in = np.array([5, -2, 25, -6, 7, 0])
        reset = np.array([0, 0, 0, 1, 0, 0])
        simulation = Simulation(sfg_accumulator, [data_in, reset])
        output0 = simulation.step()
        output1 = simulation.step()
        output2 = simulation.step()
        output3 = simulation.step()
        output4 = simulation.step()
        output5 = simulation.step()
        assert output0[0] == 0
        assert output1[0] == 5
        assert output2[0] == 3
        assert output3[0] == 28
        assert output4[0] == 0
        assert output5[0] == 7

    def test_simple_accumulator(self, sfg_simple_accumulator):
        data_in = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        simulation = Simulation(sfg_simple_accumulator, [data_in])
        simulation.run()
        assert list(simulation.results["0"]) == [
            0,
            1,
            3,
            6,
            10,
            15,
            21,
            28,
            36,
            45,
        ]

    def test_simple_filter(self, sfg_simple_filter):
        input0 = np.array([1, 2, 3, 4, 5])
        simulation = Simulation(sfg_simple_filter, [input0])
        simulation.run_for(len(input0), save_results=True)
        assert all(simulation.results["0"] == np.array([0, 1.0, 2.5, 4.25, 6.125]))

    def test_custom_operation(self, sfg_custom_operation):
        simulation = Simulation(sfg_custom_operation, [lambda n: n + 1])
        simulation.run_for(5)
        assert all(simulation.results["0"] == np.array([2, 4, 6, 8, 10]))
        assert all(simulation.results["1"] == np.array([2, 4, 8, 16, 32]))
