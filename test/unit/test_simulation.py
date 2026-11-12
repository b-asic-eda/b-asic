import numpy as np
import pytest

from b_asic.data_type import DataType, OverflowMode
from b_asic.quantization import QuantizationMode
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

        assert simulation.results["out0"][100] == 304
        assert simulation.results["out1"][100] == 505

        assert simulation.results["in0"][0] == 3
        assert simulation.results["in1"][0] == 1
        assert simulation.results["add0"][0] == 4
        assert simulation.results["add1"][0] == 5
        assert simulation.results["out0"][0] == 4
        assert simulation.results["out1"][0] == 5

        assert simulation.results["in0"][1] == 4
        assert simulation.results["in1"][1] == 3
        assert simulation.results["add0"][1] == 7
        assert simulation.results["add1"][1] == 10
        assert simulation.results["out0"][1] == 7
        assert simulation.results["out1"][1] == 10

        assert simulation.results["in0"][2] == 5
        assert simulation.results["in1"][2] == 5
        assert simulation.results["add0"][2] == 10
        assert simulation.results["add1"][2] == 15
        assert simulation.results["out0"][2] == 10
        assert simulation.results["out1"][2] == 15

        assert simulation.results["in0"][3] == 6
        assert simulation.results["in1"][3] == 7
        assert simulation.results["add0"][3] == 13
        assert simulation.results["add1"][3] == 20
        assert simulation.results["out0"][3] == 13
        assert simulation.results["out1"][3] == 20

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
        assert isinstance(simulation.results["out0"], np.ndarray)
        assert isinstance(simulation.results["out1"], np.ndarray)

        assert simulation.results["in0"][0] == 5
        assert simulation.results["in1"][0] == 7
        assert simulation.results["add0"][0] == 12
        assert simulation.results["add1"][0] == 19
        assert simulation.results["out0"][0] == 12
        assert simulation.results["out1"][0] == 19

        assert simulation.results["in0"][1] == 9
        assert simulation.results["in1"][1] == 3
        assert simulation.results["add0"][1] == 12
        assert simulation.results["add1"][1] == 15
        assert simulation.results["out0"][1] == 12
        assert simulation.results["out1"][1] == 15

        assert simulation.results["in0"][2] == 25
        assert simulation.results["in1"][2] == 3
        assert simulation.results["add0"][2] == 28
        assert simulation.results["add1"][2] == 31
        assert simulation.results["out0"][2] == 28
        assert simulation.results["out1"][2] == 31

        assert simulation.results["in0"][3] == -5
        assert simulation.results["in1"][3] == 54
        assert simulation.results["add0"][3] == 49
        assert simulation.results["add1"][3] == 103
        assert simulation.results["out0"][3] == 49
        assert simulation.results["out1"][3] == 103

        assert simulation.results["out0"][4] == 9
        assert simulation.results["out1"][4] == 11

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
        assert len(simulation.results["out0"]) == 5
        assert len(simulation.results["out1"]) == 5
        with pytest.raises(IndexError):
            simulation.step()

    def test_delay(self, sfg_delay):
        simulation = Simulation(sfg_delay)
        simulation.set_input(0, [5, -2, 25, -6, 7, 0])
        simulation.run_for(6, save_results=True)

        assert simulation.results["out0"][0] == 0
        assert simulation.results["out0"][1] == 5
        assert simulation.results["out0"][2] == -2
        assert simulation.results["out0"][3] == 25
        assert simulation.results["out0"][4] == -6
        assert simulation.results["out0"][5] == 7

    def test_delay_single_input_sequence(self, sfg_delay):
        simulation = Simulation(sfg_delay, [[5, -2, 25, -6, 7, 0]])
        simulation.run_for(6, save_results=True)

        assert simulation.results["out0"][0] == 0
        assert simulation.results["out0"][1] == 5
        assert simulation.results["out0"][2] == -2
        assert simulation.results["out0"][3] == 25
        assert simulation.results["out0"][4] == -6
        assert simulation.results["out0"][5] == 7

    def test_delay_single_input_generator(self, sfg_delay):
        simulation = Simulation(sfg_delay, [Impulse()])
        simulation.run_for(3, save_results=True)

        assert simulation.results["out0"][0] == 0
        assert simulation.results["out0"][1] == 1
        assert simulation.results["out0"][2] == 0

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

    def test_fir_filter(self):
        from b_asic.sfg_generators import fir

        h = list(range(300))
        sfg = fir(h)

        input_data = [1] + [0 for _ in range(299)]
        simulation = Simulation(sfg, input_data)
        res = simulation.run_for(len(input_data), save_results=True)
        assert res[0] == h[-1]
        assert np.allclose(simulation.results["out0"], h)


class TestRun:
    def test_save_results(self, sfg_two_inputs_two_outputs):
        simulation = Simulation(sfg_two_inputs_two_outputs, [2, 3])
        assert not simulation.results
        simulation.run_for(10, save_results=False)
        assert not simulation.results
        simulation.run_for(10)
        assert len(simulation.results["out0"]) == 10
        assert len(simulation.results["out1"]) == 10
        simulation.run_for(10, save_results=True)
        assert len(simulation.results["out0"]) == 20
        assert len(simulation.results["out1"]) == 20
        simulation.run_for(10, save_results=False)
        assert len(simulation.results["out0"]) == 20
        assert len(simulation.results["out1"]) == 20
        simulation.run_for(13, save_results=True)
        assert len(simulation.results["out0"]) == 33
        assert len(simulation.results["out1"]) == 33
        simulation.step(save_results=False)
        assert len(simulation.results["out0"]) == 33
        assert len(simulation.results["out1"]) == 33
        simulation.step()
        assert len(simulation.results["out0"]) == 34
        assert len(simulation.results["out1"]) == 34
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
        assert list(simulation.results["out0"]) == [
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
        assert all(simulation.results["out0"] == np.array([0, 1.0, 2.5, 4.25, 6.125]))

    def test_nested_sfg(self, sfg_nested_sfg):
        sim = Simulation(sfg_nested_sfg, [[1, 2, 3, 4, 5]])
        sim.run()
        assert list(sim.results["out0"]) == [0, 1, 2, 3, 4]

    def test_custom_operation(self, sfg_custom_operation):
        simulation = Simulation(sfg_custom_operation, [lambda n: n + 1])
        simulation.run_for(5)
        assert all(simulation.results["out0"] == np.array([2, 4, 6, 8, 10]))
        assert all(simulation.results["out1"] == np.array([2, 4, 8, 16, 32]))


class TestTopologicalEvaluation:
    def test_reuses_sfg_topological_order(self, sfg_delay, monkeypatch):
        from b_asic import SFG

        get_order = SFG.get_operations_topological_order
        calls = []

        def counted_get_order(self):
            calls.append(self)
            return get_order(self)

        monkeypatch.setattr(SFG, "get_operations_topological_order", counted_get_order)
        simulation = Simulation(sfg_delay, [1])
        assert simulation.run_for(3) == [1]
        assert len(calls) == 1

    def test_deep_graph(self):
        import sys

        from b_asic import SFG, Input, Output

        source = Input()
        value = source
        depth = sys.getrecursionlimit() + 100
        for _ in range(depth):
            value = value + 1
        simulation = Simulation(SFG([source], [Output(value)]), [2])
        assert simulation.step() == [depth + 2]

    def test_nested_without_recursive_evaluation(self, sfg_nested, monkeypatch):
        from b_asic import SFG

        def recursive_evaluation(*args, **kwargs):
            pytest.fail("Simulation must not call the recursive SFG evaluator")

        monkeypatch.setattr(SFG, "evaluate_output", recursive_evaluation)
        monkeypatch.setattr(SFG, "_evaluate_source", recursive_evaluation)
        simulation = Simulation(sfg_nested, [5, 7])
        assert simulation.step() == [11405]

    def test_nested_feedback(self):
        from b_asic import SFG, Delay, Input, Output

        inner_input = Input()
        inner = SFG([inner_input], [Output(Delay(inner_input, initial_value=3))])
        source = Input()
        inner <<= source + inner
        simulation = Simulation(SFG([source], [Output(inner)]), [[1, 2, 3]])
        assert simulation.run() == [6]
        np.testing.assert_array_equal(simulation.results["out0"], [3, 4, 6])
        np.testing.assert_array_equal(simulation.results["sfg0.t0"], [3, 4, 6])

    def test_nested_delay_states_are_independent(self):
        from b_asic import SFG, Delay, Input, Output

        inner_input = Input()
        inner = SFG([inner_input], [Output(Delay(inner_input))])
        source = Input()
        graph = SFG([source], [Output(inner(source) + inner(source * 2))])
        simulation = Simulation(graph, [[1, 2, 3]])
        simulation.run()
        np.testing.assert_array_equal(simulation.results["out0"], [0, 3, 6])
        assert "sfg0.t0" in simulation.results
        assert "sfg1.t0" in simulation.results

    def test_nested_finite_word_length(self, sfg_nested_sfg):
        simulation = Simulation(
            sfg_nested_sfg, [[0.25, 0.5, 0.75]], DataType(wl=(2, 4))
        )
        simulation.run()
        assert [float(v) for v in simulation.results["out0"]] == [0, 0.25, 0.5]

    def test_simultaneous_delay_updates_and_clear_state(self):
        from b_asic import SFG, Delay, Output

        first = Delay(initial_value=3)
        second = Delay(first, initial_value=7)
        first <<= second
        simulation = Simulation(SFG([], [Output(first), Output(second)]))
        assert simulation.step() == [3, 7]
        assert simulation.step() == [7, 3]
        simulation.clear_state()
        assert simulation.step() == [3, 7]

    def test_multi_output_evaluated_once(self, sfg_custom_operation, monkeypatch):
        operation = sfg_custom_operation.find_by_id("custom0")
        evaluate = type(operation).evaluate
        calls = []

        def counted_evaluate(self, *args, **kwargs):
            calls.append(args)
            return evaluate(self, *args, **kwargs)

        monkeypatch.setattr(type(operation), "evaluate", counted_evaluate)
        simulation = Simulation(sfg_custom_operation, [lambda n: n + 1])
        assert simulation.run_for(3) == [6, 8]
        assert len(calls) == 3

    def test_combinational_cycle(self):
        from b_asic import SFG, Addition, Input, Output

        source = Input()
        add = Addition(source)
        add.input(1).connect(add)
        with pytest.raises(RuntimeError, match="Direct feedback loop"):
            Simulation(SFG([source], [Output(add)]))


class TestFiniteWordLength:
    def test_accumulator_overflow(self):
        from b_asic import SFG, Delay, Input, Output

        in0 = Input()
        d = Delay()
        d <<= in0 + d
        out0 = Output(d)
        sfg = SFG([in0], [out0])

        sim1 = Simulation(sfg, [lambda n: n / 16])
        sim1.run_for(10)

        sim2 = Simulation(sfg, [lambda n: n / 16], DataType(wl=8))
        sim2.run_for(10)

        unsigned_err = sim2.results["out0"] - sim1.results["out0"]
        assert all(unsigned_err == 0)  # no error unless cast to float is done

        err = [float(e) for e in sim2.results["out0"]] - sim1.results["out0"]
        assert all(
            err[:7] == 0
        )  # no error in first 7 iterations due to sufficient word length
        assert all(err[7:] != 0)  # overflow occurs at iteration 8

    def test_accumulator_saturation(self):
        from b_asic import SFG, Delay, Input, Output

        in0 = Input()
        d = Delay()
        d <<= in0 + d
        out0 = Output(d)
        sfg = SFG([in0], [out0])

        sim1 = Simulation(sfg, [lambda n: n / 16])
        sim1.run_for(10)

        sim2 = Simulation(
            sfg,
            [lambda n: n / 16],
            DataType(
                wl=8,
                overflow_mode=OverflowMode.SATURATION,
            ),
        )
        sim2.run_for(10)

        unsigned_err = sim2.results["out0"] - sim1.results["out0"]
        assert all(unsigned_err[:7] == 0)
        assert all(unsigned_err[7:] != 0)  # saturation occurs after iteration 8

        err = [float(e) for e in sim2.results["out0"]] - sim1.results["out0"]
        assert all(
            err[:7] == 0
        )  # no error in first 7 iterations due to sufficient word length
        assert all(err[7:] != 0)  # saturation occurs after iteration 8

        assert all(
            float(sim2.results["out0"][i]) == 1 - 2**-7 for i in range(8, 10)
        )  # saturated value

        sim3 = Simulation(sfg, [lambda n: n / 16])
        sim3.run_for(20)

        sim4 = Simulation(
            sfg,
            [lambda n: n / 16],
            DataType(
                wl=(2, 6),
                overflow_mode=OverflowMode.SATURATION,
            ),
        )
        sim4.run_for(20)

        err = [float(e) for e in sim4.results["out0"]] - sim3.results["out0"]
        assert all(
            err[:9] == 0
        )  # no error in first 9 iterations due to sufficient word length
        assert all(err[9:] != 0)  # saturation occurs after iteration 9
        assert all(
            float(sim4.results["out0"][i]) == 2 - 2**-6 for i in range(9, 20)
        )  # saturated value

    def test_iir_impulse_response(self, sfg_direct_form_iir_lp_filter):
        sim1 = Simulation(sfg_direct_form_iir_lp_filter, [[1.0] + [0.0] * 19])
        sim1.run()

        dt = DataType(wl=(2, 4))
        sim2 = Simulation(sfg_direct_form_iir_lp_filter, [[1.0] + [0.0] * 19], dt)
        sim2.run()

        err = [float(e) for e in sim2.results["out0"]] - sim1.results["out0"]

        assert all(err != 0)
        assert all(abs(err) > 10e-6)

    def test_iir_impulse_response_magnitude_truncation(
        self, sfg_direct_form_iir_lp_filter
    ):
        dt = DataType(
            wl=(3, 7),
            quantization_mode=QuantizationMode.TRUNCATION,
        )
        sim1 = Simulation(sfg_direct_form_iir_lp_filter, [[1.0] + [0.0] * 19], dt)
        sim1.run()

        dt = DataType(
            wl=(3, 7),
            quantization_mode=QuantizationMode.MAGNITUDE_TRUNCATION,
        )
        sim2 = Simulation(sfg_direct_form_iir_lp_filter, [[1.0] + [0.0] * 19], dt)
        sim2.run()

        err = np.array([float(e) for e in sim2.results["out0"]]) - np.array(
            [float(e) for e in sim1.results["out0"]]
        )

        assert any(err != 0)
        assert all(
            err >= 0
        )  # no negative errors with magnitude truncation compared to truncation
