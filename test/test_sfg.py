import io
import random
import string
import sys
from os import path, remove

import pytest

from b_asic import SFG, FastSimulation, Input, Output, Signal
from b_asic.core_operations import (
    Absolute,
    Addition,
    Butterfly,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Division,
    Max,
    Min,
    Multiplication,
    SquareRoot,
    Subtraction,
    SymmetricTwoportAdaptor,
)
from b_asic.save_load_structure import python_to_sfg, sfg_to_python


class TestInit:
    def test_direct_input_to_output_sfg_construction(self):
        in1 = Input("IN1")
        out1 = Output(None, "OUT1")
        out1.input(0).connect(in1, "S1")

        sfg = SFG(inputs=[in1], outputs=[out1])  # in1 ---s1---> out1

        assert len(list(sfg.components)) == 3
        assert len(list(sfg.operations)) == 2
        assert sfg.input_count == 1
        assert sfg.output_count == 1

    def test_same_signal_input_and_output_sfg_construction(self):
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")

        s1 = add2.input(0).connect(add1, "S1")

        # in1 ---s1---> out1
        sfg = SFG(input_signals=[s1], output_signals=[s1])

        assert len(list(sfg.components)) == 3
        assert len(list(sfg.operations)) == 2
        assert sfg.input_count == 1
        assert sfg.output_count == 1

    def test_outputs_construction(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])

        assert len(list(sfg.components)) == 7
        assert len(list(sfg.operations)) == 4
        assert sfg.input_count == 0
        assert sfg.output_count == 1

    def test_signals_construction(self, operation_tree):
        sfg = SFG(output_signals=[Signal(source=operation_tree.output(0))])

        assert len(list(sfg.components)) == 7
        assert len(list(sfg.operations)) == 4
        assert sfg.input_count == 0
        assert sfg.output_count == 1


class TestPrintSfg:
    def test_one_addition(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        add1 = Addition(inp1, inp2, "ADD1")
        out1 = Output(add1, "OUT1")
        sfg = SFG(inputs=[inp1, inp2], outputs=[out1], name="SFG1")

        assert (
            sfg.__str__()
            == "id: no_id, \tname: SFG1, \tinputs: {0: '-'}, \toutputs: {0:"
            " '-'}\n"
            + "Internal Operations:\n"
            + "----------------------------------------------------------------------------------------------------\n"
            + str(sfg.find_by_name("INP1")[0])
            + "\n"
            + str(sfg.find_by_name("INP2")[0])
            + "\n"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg.find_by_name("OUT1")[0])
            + "\n"
            + "----------------------------------------------------------------------------------------------------\n"
        )

    def test_add_mul(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(inp1, inp2, "ADD1")
        mul1 = Multiplication(add1, inp3, "MUL1")
        out1 = Output(mul1, "OUT1")
        sfg = SFG(inputs=[inp1, inp2, inp3], outputs=[out1], name="mac_sfg")

        assert (
            sfg.__str__()
            == "id: no_id, \tname: mac_sfg, \tinputs: {0: '-'}, \toutputs: {0:"
            " '-'}\n"
            + "Internal Operations:\n"
            + "----------------------------------------------------------------------------------------------------\n"
            + str(sfg.find_by_name("INP1")[0])
            + "\n"
            + str(sfg.find_by_name("INP2")[0])
            + "\n"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg.find_by_name("INP3")[0])
            + "\n"
            + str(sfg.find_by_name("MUL1")[0])
            + "\n"
            + str(sfg.find_by_name("OUT1")[0])
            + "\n"
            + "----------------------------------------------------------------------------------------------------\n"
        )

    def test_constant(self):
        inp1 = Input("INP1")
        const1 = Constant(3, "CONST")
        add1 = Addition(const1, inp1, "ADD1")
        out1 = Output(add1, "OUT1")

        sfg = SFG(inputs=[inp1], outputs=[out1], name="sfg")

        assert (
            sfg.__str__()
            == "id: no_id, \tname: sfg, \tinputs: {0: '-'}, \toutputs: {0:"
            " '-'}\n"
            + "Internal Operations:\n"
            + "----------------------------------------------------------------------------------------------------\n"
            + str(sfg.find_by_name("CONST")[0])
            + "\n"
            + str(sfg.find_by_name("INP1")[0])
            + "\n"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg.find_by_name("OUT1")[0])
            + "\n"
            + "----------------------------------------------------------------------------------------------------\n"
        )

    def test_simple_filter(self, sfg_simple_filter):
        assert (
            sfg_simple_filter.__str__()
            == "id: no_id, \tname: simple_filter, \tinputs: {0: '-'},"
            " \toutputs: {0: '-'}\n"
            + "Internal Operations:\n"
            + "----------------------------------------------------------------------------------------------------\n"
            + str(sfg_simple_filter.find_by_name("IN1")[0])
            + "\n"
            + str(sfg_simple_filter.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg_simple_filter.find_by_name("T1")[0])
            + "\n"
            + str(sfg_simple_filter.find_by_name("CMUL1")[0])
            + "\n"
            + str(sfg_simple_filter.find_by_name("OUT1")[0])
            + "\n"
            + "----------------------------------------------------------------------------------------------------\n"
        )


class TestDeepCopy:
    def test_deep_copy_no_duplicates(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(inp1, inp2, "ADD1")
        mul1 = Multiplication(add1, inp3, "MUL1")
        out1 = Output(mul1, "OUT1")

        mac_sfg = SFG(inputs=[inp1, inp2], outputs=[out1], name="mac_sfg")
        mac_sfg_new = mac_sfg()

        assert mac_sfg.name == "mac_sfg"
        assert mac_sfg_new.name == ""

        for g_id, component in mac_sfg._components_by_id.items():
            component_copy = mac_sfg_new.find_by_id(g_id)
            assert component.name == component_copy.name

    def test_deep_copy(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")
        mul1 = Multiplication(None, None, "MUL1")
        out1 = Output(None, "OUT1")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S4")
        add2.input(1).connect(inp3, "S3")
        mul1.input(0).connect(add1, "S5")
        mul1.input(1).connect(add2, "S6")
        out1.input(0).connect(mul1, "S7")

        mac_sfg = SFG(
            inputs=[inp1, inp2],
            outputs=[out1],
            id_number_offset=100,
            name="mac_sfg",
        )
        mac_sfg_new = mac_sfg(name="mac_sfg2")

        assert mac_sfg.name == "mac_sfg"
        assert mac_sfg_new.name == "mac_sfg2"
        assert mac_sfg.id_number_offset == 100
        assert mac_sfg_new.id_number_offset == 100

        for g_id, component in mac_sfg._components_by_id.items():
            component_copy = mac_sfg_new.find_by_id(g_id)
            assert component.name == component_copy.name

    def test_deep_copy_with_new_sources(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(inp1, inp2, "ADD1")
        mul1 = Multiplication(add1, inp3, "MUL1")
        out1 = Output(mul1, "OUT1")

        mac_sfg = SFG(inputs=[inp1, inp2], outputs=[out1], name="mac_sfg")

        a = Addition(Constant(3), Constant(5))
        b = Constant(2)
        mac_sfg_new = mac_sfg(a, b)
        assert mac_sfg_new.input(0).signals[0].source.operation is a
        assert mac_sfg_new.input(1).signals[0].source.operation is b


class TestEvaluateOutput:
    def test_evaluate_output(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])
        assert sfg.evaluate_output(0, []) == 5

    def test_evaluate_output_large(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        assert sfg.evaluate_output(0, []) == 14

    def test_evaluate_output_cycle(self, operation_graph_with_cycle):
        sfg = SFG(outputs=[Output(operation_graph_with_cycle)])
        with pytest.raises(
            RuntimeError, match="Direct feedback loop detected"
        ):
            sfg.evaluate_output(0, [])


class TestComponents:
    def test_advanced_components(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")
        mul1 = Multiplication(None, None, "MUL1")
        out1 = Output(None, "OUT1")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S4")
        add2.input(1).connect(inp3, "S3")
        mul1.input(0).connect(add1, "S5")
        mul1.input(1).connect(add2, "S6")
        out1.input(0).connect(mul1, "S7")

        mac_sfg = SFG(inputs=[inp1, inp2], outputs=[out1], name="mac_sfg")

        assert {comp.name for comp in mac_sfg.components} == {
            "INP1",
            "INP2",
            "INP3",
            "ADD1",
            "ADD2",
            "MUL1",
            "OUT1",
            "S1",
            "S2",
            "S3",
            "S4",
            "S5",
            "S6",
            "S7",
        }


class TestReplaceComponents:
    def test_replace_addition_by_id(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])
        component_id = "add1"

        sfg = sfg.replace_component(
            Multiplication(name="Multi"), graph_id=component_id
        )
        assert component_id not in sfg._components_by_id.keys()
        assert "Multi" in sfg._components_by_name.keys()

    def test_replace_addition_large_tree(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "add3"

        sfg = sfg.replace_component(
            Multiplication(name="Multi"), graph_id=component_id
        )
        assert "Multi" in sfg._components_by_name.keys()
        assert component_id not in sfg._components_by_id.keys()

    def test_replace_no_input_component(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])
        component_id = "c1"
        const_ = sfg.find_by_id(component_id)

        sfg = sfg.replace_component(Constant(1), graph_id=component_id)
        assert const_ is not sfg.find_by_id(component_id)

    def test_no_match_on_replace(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "addd1"

        try:
            sfg = sfg.replace_component(
                Multiplication(name="Multi"), graph_id=component_id
            )
        except AssertionError:
            assert True
        else:
            assert False

    def test_not_equal_input(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "c1"

        try:
            sfg = sfg.replace_component(
                Multiplication(name="Multi"), graph_id=component_id
            )
        except AssertionError:
            assert True
        else:
            assert False


class TestConstructSFG:
    def test_1k_additions(self):
        prev_op = Addition(Constant(1), Constant(1))
        for _ in range(999):
            prev_op = Addition(prev_op, Constant(2))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 2000

    def test_1k_subtractions(self):
        prev_op = Subtraction(Constant(0), Constant(2))
        for _ in range(999):
            prev_op = Subtraction(prev_op, Constant(2))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == -2000

    def test_1k_butterfly(self):
        prev_op_add = Addition(Constant(1), Constant(1))
        prev_op_sub = Subtraction(Constant(-1), Constant(1))
        for _ in range(499):
            prev_op_add = Addition(prev_op_add, Constant(2))
        for _ in range(499):
            prev_op_sub = Subtraction(prev_op_sub, Constant(2))
        butterfly = Butterfly(prev_op_add, prev_op_sub)
        sfg = SFG(
            outputs=[Output(butterfly.output(0)), Output(butterfly.output(1))]
        )
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 0
        assert sim.results["1"][0].real == 2000

    def test_1k_multiplications(self):
        prev_op = Multiplication(Constant(3), Constant(0.5))
        for _ in range(999):
            prev_op = Multiplication(prev_op, Constant(1.01))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 31127.458868040336

    def test_1k_divisions(self):
        prev_op = Division(Constant(3), Constant(0.5))
        for _ in range(999):
            prev_op = Division(prev_op, Constant(1.01))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 0.00028913378500165966

    def test_1k_mins(self):
        prev_op = Min(Constant(3.14159), Constant(43.14123843))
        for _ in range(999):
            prev_op = Min(prev_op, Constant(43.14123843))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 3.14159

    def test_1k_maxs(self):
        prev_op = Max(Constant(3.14159), Constant(43.14123843))
        for _ in range(999):
            prev_op = Max(prev_op, Constant(3.14159))
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 43.14123843

    def test_1k_square_roots(self):
        prev_op = SquareRoot(Constant(1000000))
        for _ in range(4):
            prev_op = SquareRoot(prev_op)
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 1.539926526059492

    def test_1k_complex_conjugates(self):
        prev_op = ComplexConjugate(Constant(10 + 5j))
        for _ in range(999):
            prev_op = ComplexConjugate(prev_op)
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"] == [10 + 5j]

    def test_1k_absolutes(self):
        prev_op = Absolute(Constant(-3.14159))
        for _ in range(999):
            prev_op = Absolute(prev_op)
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 3.14159

    def test_1k_constant_multiplications(self):
        prev_op = ConstantMultiplication(1.02, Constant(3.14159))
        for _ in range(999):
            prev_op = ConstantMultiplication(1.02, prev_op)
        sfg = SFG(outputs=[Output(prev_op)])
        sim = FastSimulation(sfg)
        sim.step()
        assert sim.results["0"][0].real == 1251184247.0026844


class TestInsertComponent:
    def test_insert_component_in_sfg(self, large_operation_tree_names):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        sqrt = SquareRoot()

        _sfg = sfg.insert_operation(
            sqrt, sfg.find_by_name("constant4")[0].graph_id
        )
        assert _sfg.evaluate() != sfg.evaluate()

        assert any([isinstance(comp, SquareRoot) for comp in _sfg.operations])
        assert not any(
            [isinstance(comp, SquareRoot) for comp in sfg.operations]
        )

        assert not isinstance(
            sfg.find_by_name("constant4")[0]
            .output(0)
            .signals[0]
            .destination.operation,
            SquareRoot,
        )
        assert isinstance(
            _sfg.find_by_name("constant4")[0]
            .output(0)
            .signals[0]
            .destination.operation,
            SquareRoot,
        )

        assert sfg.find_by_name("constant4")[0].output(0).signals[
            0
        ].destination.operation is sfg.find_by_id("add3")
        assert _sfg.find_by_name("constant4")[0].output(0).signals[
            0
        ].destination.operation is not _sfg.find_by_id("add3")
        assert _sfg.find_by_id("sqrt1").output(0).signals[
            0
        ].destination.operation is _sfg.find_by_id("add3")

    def test_insert_invalid_component_in_sfg(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])

        # Should raise an exception for not matching input count to output count.
        add4 = Addition()
        with pytest.raises(TypeError, match="Source operation output count"):
            sfg.insert_operation(add4, "c1")

    def test_insert_at_output(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])

        # Should raise an exception for trying to insert an operation after an output.
        sqrt = SquareRoot()
        with pytest.raises(TypeError, match="Source operation cannot be an"):
            _ = sfg.insert_operation(sqrt, "out1")

    def test_insert_multiple_output_ports(self, butterfly_operation_tree):
        sfg = SFG(outputs=list(map(Output, butterfly_operation_tree.outputs)))
        _sfg = sfg.insert_operation(Butterfly(name="n_bfly"), "bfly3")

        assert sfg.evaluate() != _sfg.evaluate()

        assert len(sfg.find_by_name("n_bfly")) == 0
        assert len(_sfg.find_by_name("n_bfly")) == 1

        # Correctly connected old output -> new input
        assert (
            _sfg.find_by_name("bfly3")[0]
            .output(0)
            .signals[0]
            .destination.operation
            is _sfg.find_by_name("n_bfly")[0]
        )
        assert (
            _sfg.find_by_name("bfly3")[0]
            .output(1)
            .signals[0]
            .destination.operation
            is _sfg.find_by_name("n_bfly")[0]
        )

        # Correctly connected new input -> old output
        assert (
            _sfg.find_by_name("n_bfly")[0].input(0).signals[0].source.operation
            is _sfg.find_by_name("bfly3")[0]
        )
        assert (
            _sfg.find_by_name("n_bfly")[0].input(1).signals[0].source.operation
            is _sfg.find_by_name("bfly3")[0]
        )

        # Correctly connected new output -> next input
        assert (
            _sfg.find_by_name("n_bfly")[0]
            .output(0)
            .signals[0]
            .destination.operation
            is _sfg.find_by_name("bfly2")[0]
        )
        assert (
            _sfg.find_by_name("n_bfly")[0]
            .output(1)
            .signals[0]
            .destination.operation
            is _sfg.find_by_name("bfly2")[0]
        )

        # Correctly connected next input -> new output
        assert (
            _sfg.find_by_name("bfly2")[0].input(0).signals[0].source.operation
            is _sfg.find_by_name("n_bfly")[0]
        )
        assert (
            _sfg.find_by_name("bfly2")[0].input(1).signals[0].source.operation
            is _sfg.find_by_name("n_bfly")[0]
        )


class TestFindComponentsWithTypeName:
    def test_mac_components(self):
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")
        mul1 = Multiplication(None, None, "MUL1")
        out1 = Output(None, "OUT1")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S4")
        add2.input(1).connect(inp3, "S3")
        mul1.input(0).connect(add1, "S5")
        mul1.input(1).connect(add2, "S6")
        out1.input(0).connect(mul1, "S7")

        mac_sfg = SFG(inputs=[inp1, inp2], outputs=[out1], name="mac_sfg")

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(inp1.type_name())
        } == {
            "INP1",
            "INP2",
            "INP3",
        }

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(add1.type_name())
        } == {
            "ADD1",
            "ADD2",
        }

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(mul1.type_name())
        } == {"MUL1"}

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(out1.type_name())
        } == {"OUT1"}

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(Signal.type_name())
        } == {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}


class TestGetPrecedenceList:
    def test_inputs_delays(self, precedence_sfg_delays):
        precedence_list = precedence_sfg_delays.get_precedence_list()

        assert len(precedence_list) == 7

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[0]
            ]
        ) == {"IN1", "T1", "T2"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[1]
            ]
        ) == {"C0", "B1", "B2", "A1", "A2"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[2]
            ]
        ) == {"ADD2", "ADD3"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[3]
            ]
        ) == {"ADD1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[4]
            ]
        ) == {"Q1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[5]
            ]
        ) == {"A0"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[6]
            ]
        ) == {"ADD4"}

    def test_inputs_constants_delays_multiple_outputs(
        self, precedence_sfg_delays_and_constants
    ):
        precedence_list = (
            precedence_sfg_delays_and_constants.get_precedence_list()
        )

        assert len(precedence_list) == 7

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[0]
            ]
        ) == {"IN1", "T1", "CONST1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[1]
            ]
        ) == {"C0", "B1", "B2", "A1", "A2"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[2]
            ]
        ) == {"ADD2", "ADD3"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[3]
            ]
        ) == {"ADD1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[4]
            ]
        ) == {"Q1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[5]
            ]
        ) == {"A0"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[6]
            ]
        ) == {"BFLY1.0", "BFLY1.1"}

    def test_precedence_multiple_outputs_same_precedence(
        self, sfg_two_inputs_two_outputs
    ):
        sfg_two_inputs_two_outputs.name = "NESTED_SFG"

        in1 = Input("IN1")
        sfg_two_inputs_two_outputs.input(0).connect(in1, "S1")
        in2 = Input("IN2")
        cmul1 = ConstantMultiplication(10, None, "CMUL1")
        cmul1.input(0).connect(in2, "S2")
        sfg_two_inputs_two_outputs.input(1).connect(cmul1, "S3")

        out1 = Output(sfg_two_inputs_two_outputs.output(0), "OUT1")
        out2 = Output(sfg_two_inputs_two_outputs.output(1), "OUT2")

        sfg = SFG(inputs=[in1, in2], outputs=[out1, out2])

        precedence_list = sfg.get_precedence_list()

        assert len(precedence_list) == 3

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[0]
            ]
        ) == {"IN1", "IN2"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[1]
            ]
        ) == {"CMUL1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[2]
            ]
        ) == {"NESTED_SFG.0", "NESTED_SFG.1"}

    def test_precedence_sfg_multiple_outputs_different_precedences(
        self, sfg_two_inputs_two_outputs_independent
    ):
        sfg_two_inputs_two_outputs_independent.name = "NESTED_SFG"

        in1 = Input("IN1")
        in2 = Input("IN2")
        sfg_two_inputs_two_outputs_independent.input(0).connect(in1, "S1")
        cmul1 = ConstantMultiplication(10, None, "CMUL1")
        cmul1.input(0).connect(in2, "S2")
        sfg_two_inputs_two_outputs_independent.input(1).connect(cmul1, "S3")
        out1 = Output(sfg_two_inputs_two_outputs_independent.output(0), "OUT1")
        out2 = Output(sfg_two_inputs_two_outputs_independent.output(1), "OUT2")

        sfg = SFG(inputs=[in1, in2], outputs=[out1, out2])

        precedence_list = sfg.get_precedence_list()

        assert len(precedence_list) == 3

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[0]
            ]
        ) == {"IN1", "IN2"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[1]
            ]
        ) == {"CMUL1"}

        assert set(
            [
                port.operation.key(port.index, port.operation.name)
                for port in precedence_list[2]
            ]
        ) == {"NESTED_SFG.0", "NESTED_SFG.1"}


class TestPrintPrecedence:
    def test_delays(self, precedence_sfg_delays):
        sfg = precedence_sfg_delays

        captured_output = io.StringIO()
        sys.stdout = captured_output

        sfg.print_precedence_graph()

        sys.stdout = sys.__stdout__

        captured_output = captured_output.getvalue()

        assert (
            captured_output
            == "-" * 120
            + "\n"
            + "1.1 \t"
            + str(sfg.find_by_name("IN1")[0])
            + "\n"
            + "1.2 \t"
            + str(sfg.find_by_name("T1")[0])
            + "\n"
            + "1.3 \t"
            + str(sfg.find_by_name("T2")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "2.1 \t"
            + str(sfg.find_by_name("C0")[0])
            + "\n"
            + "2.2 \t"
            + str(sfg.find_by_name("A1")[0])
            + "\n"
            + "2.3 \t"
            + str(sfg.find_by_name("B1")[0])
            + "\n"
            + "2.4 \t"
            + str(sfg.find_by_name("A2")[0])
            + "\n"
            + "2.5 \t"
            + str(sfg.find_by_name("B2")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "3.1 \t"
            + str(sfg.find_by_name("ADD3")[0])
            + "\n"
            + "3.2 \t"
            + str(sfg.find_by_name("ADD2")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "4.1 \t"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "5.1 \t"
            + str(sfg.find_by_name("Q1")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "6.1 \t"
            + str(sfg.find_by_name("A0")[0])
            + "\n"
            + "-" * 120
            + "\n"
            + "7.1 \t"
            + str(sfg.find_by_name("ADD4")[0])
            + "\n"
            + "-" * 120
            + "\n"
        )


class TestDepends:
    def test_depends_sfg(self, sfg_two_inputs_two_outputs):
        assert set(
            sfg_two_inputs_two_outputs.inputs_required_for_output(0)
        ) == {0, 1}
        assert set(
            sfg_two_inputs_two_outputs.inputs_required_for_output(1)
        ) == {0, 1}

    def test_depends_sfg_independent(
        self, sfg_two_inputs_two_outputs_independent
    ):
        assert set(
            sfg_two_inputs_two_outputs_independent.inputs_required_for_output(
                0
            )
        ) == {0}
        assert set(
            sfg_two_inputs_two_outputs_independent.inputs_required_for_output(
                1
            )
        ) == {1}


class TestConnectExternalSignalsToComponentsSoloComp:
    def test_connect_external_signals_to_components_mac(self):
        """Replace a MAC with inner components in an SFG"""
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")
        mul1 = Multiplication(None, None, "MUL1")
        out1 = Output(None, "OUT1")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S3")
        add2.input(1).connect(inp3, "S4")
        mul1.input(0).connect(add1, "S5")
        mul1.input(1).connect(add2, "S6")
        out1.input(0).connect(mul1, "S7")

        mac_sfg = SFG(inputs=[inp1, inp2], outputs=[out1])

        inp4 = Input("INP4")
        inp5 = Input("INP5")
        out2 = Output(None, "OUT2")

        mac_sfg.input(0).connect(inp4, "S8")
        mac_sfg.input(1).connect(inp5, "S9")
        out2.input(0).connect(mac_sfg.outputs[0], "S10")

        test_sfg = SFG(inputs=[inp4, inp5], outputs=[out2])
        assert test_sfg.evaluate(1, 2) == 9
        mac_sfg.connect_external_signals_to_components()
        assert test_sfg.evaluate(1, 2) == 9
        assert not test_sfg.connect_external_signals_to_components()

    def test_connect_external_signals_to_components_operation_tree(
        self, operation_tree
    ):
        """Replaces an SFG with only a operation_tree component with its inner components
        """
        sfg1 = SFG(outputs=[Output(operation_tree)])
        out1 = Output(None, "OUT1")
        out1.input(0).connect(sfg1.outputs[0], "S1")
        test_sfg = SFG(outputs=[out1])
        assert test_sfg.evaluate_output(0, []) == 5
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate_output(0, []) == 5
        assert not test_sfg.connect_external_signals_to_components()

    def test_connect_external_signals_to_components_large_operation_tree(
        self, large_operation_tree
    ):
        """Replaces an SFG with only a large_operation_tree component with its inner components
        """
        sfg1 = SFG(outputs=[Output(large_operation_tree)])
        out1 = Output(None, "OUT1")
        out1.input(0).connect(sfg1.outputs[0], "S1")
        test_sfg = SFG(outputs=[out1])
        assert test_sfg.evaluate_output(0, []) == 14
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate_output(0, []) == 14
        assert not test_sfg.connect_external_signals_to_components()


class TestConnectExternalSignalsToComponentsMultipleComp:
    def test_connect_external_signals_to_components_operation_tree(
        self, operation_tree
    ):
        """Replaces a operation_tree in an SFG with other components"""
        sfg1 = SFG(outputs=[Output(operation_tree)])

        inp1 = Input("INP1")
        inp2 = Input("INP2")
        out1 = Output(None, "OUT1")

        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S3")
        add2.input(1).connect(sfg1.outputs[0], "S4")
        out1.input(0).connect(add2, "S5")

        test_sfg = SFG(inputs=[inp1, inp2], outputs=[out1])
        assert test_sfg.evaluate(1, 2) == 8
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate(1, 2) == 8
        assert not test_sfg.connect_external_signals_to_components()

    def test_connect_external_signals_to_components_large_operation_tree(
        self, large_operation_tree
    ):
        """Replaces a large_operation_tree in an SFG with other components"""
        sfg1 = SFG(outputs=[Output(large_operation_tree)])

        inp1 = Input("INP1")
        inp2 = Input("INP2")
        out1 = Output(None, "OUT1")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S3")
        add2.input(1).connect(sfg1.outputs[0], "S4")
        out1.input(0).connect(add2, "S5")

        test_sfg = SFG(inputs=[inp1, inp2], outputs=[out1])
        assert test_sfg.evaluate(1, 2) == 17
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate(1, 2) == 17
        assert not test_sfg.connect_external_signals_to_components()

    def create_sfg(self, op_tree):
        """Create a simple SFG with either operation_tree or large_operation_tree
        """
        sfg1 = SFG(outputs=[Output(op_tree)])

        inp1 = Input("INP1")
        inp2 = Input("INP2")
        out1 = Output(None, "OUT1")
        add1 = Addition(None, None, "ADD1")
        add2 = Addition(None, None, "ADD2")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")
        add2.input(0).connect(add1, "S3")
        add2.input(1).connect(sfg1.outputs[0], "S4")
        out1.input(0).connect(add2, "S5")

        return SFG(inputs=[inp1, inp2], outputs=[out1])

    def test_connect_external_signals_to_components_many_op(
        self, large_operation_tree
    ):
        """Replaces an sfg component in a larger SFG with several component operations
        """
        inp1 = Input("INP1")
        inp2 = Input("INP2")
        inp3 = Input("INP3")
        inp4 = Input("INP4")
        out1 = Output(None, "OUT1")
        add1 = Addition(None, None, "ADD1")
        sub1 = Subtraction(None, None, "SUB1")

        add1.input(0).connect(inp1, "S1")
        add1.input(1).connect(inp2, "S2")

        sfg1 = self.create_sfg(large_operation_tree)

        sfg1.input(0).connect(add1, "S3")
        sfg1.input(1).connect(inp3, "S4")
        sub1.input(0).connect(sfg1.outputs[0], "S5")
        sub1.input(1).connect(inp4, "S6")
        out1.input(0).connect(sub1, "S7")

        test_sfg = SFG(inputs=[inp1, inp2, inp3, inp4], outputs=[out1])

        assert test_sfg.evaluate(1, 2, 3, 4) == 16
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate(1, 2, 3, 4) == 16
        assert not test_sfg.connect_external_signals_to_components()


class TestTopologicalOrderOperations:
    def test_feedback_sfg(self, sfg_simple_filter):
        topological_order = (
            sfg_simple_filter.get_operations_topological_order()
        )

        assert [comp.name for comp in topological_order] == [
            "IN1",
            "ADD1",
            "T1",
            "CMUL1",
            "OUT1",
        ]

    def test_multiple_independent_inputs(
        self, sfg_two_inputs_two_outputs_independent
    ):
        topological_order = (
            sfg_two_inputs_two_outputs_independent.get_operations_topological_order()
        )

        assert [comp.name for comp in topological_order] == [
            "IN1",
            "OUT1",
            "IN2",
            "C1",
            "ADD1",
            "OUT2",
        ]

    def test_complex_graph(self, precedence_sfg_delays):
        topological_order = (
            precedence_sfg_delays.get_operations_topological_order()
        )

        assert [comp.name for comp in topological_order] == [
            "IN1",
            "C0",
            "ADD1",
            "Q1",
            "A0",
            "T1",
            "B1",
            "A1",
            "T2",
            "B2",
            "ADD2",
            "A2",
            "ADD3",
            "ADD4",
            "OUT1",
        ]


class TestRemove:
    def test_remove_single_input_outputs(self, sfg_simple_filter):
        new_sfg = sfg_simple_filter.remove_operation("cmul1")

        assert set(
            op.name
            for op in sfg_simple_filter.find_by_name("T1")[
                0
            ].subsequent_operations
        ) == {"CMUL1", "OUT1"}
        assert set(
            op.name
            for op in new_sfg.find_by_name("T1")[0].subsequent_operations
        ) == {"ADD1", "OUT1"}

        assert set(
            op.name
            for op in sfg_simple_filter.find_by_name("ADD1")[
                0
            ].preceding_operations
        ) == {"CMUL1", "IN1"}
        assert set(
            op.name
            for op in new_sfg.find_by_name("ADD1")[0].preceding_operations
        ) == {"T1", "IN1"}

        assert "S1" in set(
            [
                sig.name
                for sig in sfg_simple_filter.find_by_name("T1")[0]
                .output(0)
                .signals
            ]
        )
        assert "S2" in set(
            [
                sig.name
                for sig in new_sfg.find_by_name("T1")[0].output(0).signals
            ]
        )

    def test_remove_multiple_inputs_outputs(self, butterfly_operation_tree):
        out1 = Output(butterfly_operation_tree.output(0), "OUT1")
        out2 = Output(butterfly_operation_tree.output(1), "OUT2")

        sfg = SFG(outputs=[out1, out2])

        new_sfg = sfg.remove_operation(sfg.find_by_name("bfly2")[0].graph_id)

        assert sfg.find_by_name("bfly3")[0].output(0).signal_count == 1
        assert new_sfg.find_by_name("bfly3")[0].output(0).signal_count == 1

        sfg_dest_0 = (
            sfg.find_by_name("bfly3")[0].output(0).signals[0].destination
        )
        new_sfg_dest_0 = (
            new_sfg.find_by_name("bfly3")[0].output(0).signals[0].destination
        )

        assert sfg_dest_0.index == 0
        assert new_sfg_dest_0.index == 0
        assert sfg_dest_0.operation.name == "bfly2"
        assert new_sfg_dest_0.operation.name == "bfly1"

        assert sfg.find_by_name("bfly3")[0].output(1).signal_count == 1
        assert new_sfg.find_by_name("bfly3")[0].output(1).signal_count == 1

        sfg_dest_1 = (
            sfg.find_by_name("bfly3")[0].output(1).signals[0].destination
        )
        new_sfg_dest_1 = (
            new_sfg.find_by_name("bfly3")[0].output(1).signals[0].destination
        )

        assert sfg_dest_1.index == 1
        assert new_sfg_dest_1.index == 1
        assert sfg_dest_1.operation.name == "bfly2"
        assert new_sfg_dest_1.operation.name == "bfly1"

        assert sfg.find_by_name("bfly1")[0].input(0).signal_count == 1
        assert new_sfg.find_by_name("bfly1")[0].input(0).signal_count == 1

        sfg_source_0 = sfg.find_by_name("bfly1")[0].input(0).signals[0].source
        new_sfg_source_0 = (
            new_sfg.find_by_name("bfly1")[0].input(0).signals[0].source
        )

        assert sfg_source_0.index == 0
        assert new_sfg_source_0.index == 0
        assert sfg_source_0.operation.name == "bfly2"
        assert new_sfg_source_0.operation.name == "bfly3"

        sfg_source_1 = sfg.find_by_name("bfly1")[0].input(1).signals[0].source
        new_sfg_source_1 = (
            new_sfg.find_by_name("bfly1")[0].input(1).signals[0].source
        )

        assert sfg_source_1.index == 1
        assert new_sfg_source_1.index == 1
        assert sfg_source_1.operation.name == "bfly2"
        assert new_sfg_source_1.operation.name == "bfly3"

        assert "bfly2" not in set(op.name for op in new_sfg.operations)

    def remove_different_number_inputs_outputs(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.remove_operation("add1")


class TestSaveLoadSFG:
    def get_path(self, existing=False):
        path_ = "".join(random.choices(string.ascii_uppercase, k=4)) + ".py"
        while path.exists(path_) if not existing else not path.exists(path_):
            path_ = (
                "".join(random.choices(string.ascii_uppercase, k=4)) + ".py"
            )

        return path_

    def test_save_simple_sfg(self, sfg_simple_filter):
        result = sfg_to_python(sfg_simple_filter)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        with open(path_, "r") as file_obj:
            assert file_obj.read() == result

        remove(path_)

    def test_save_complex_sfg(self, precedence_sfg_delays_and_constants):
        result = sfg_to_python(precedence_sfg_delays_and_constants)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        with open(path_, "r") as file_obj:
            assert file_obj.read() == result

        remove(path_)

    def test_load_simple_sfg(self, sfg_simple_filter):
        result = sfg_to_python(sfg_simple_filter)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        simple_filter_, _ = python_to_sfg(path_)

        assert str(sfg_simple_filter) == str(simple_filter_)
        assert sfg_simple_filter.evaluate([2]) == simple_filter_.evaluate([2])

        remove(path_)

    def test_load_complex_sfg(self, precedence_sfg_delays_and_constants):
        result = sfg_to_python(precedence_sfg_delays_and_constants)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        precedence_sfg_registers_and_constants_, _ = python_to_sfg(path_)

        assert str(precedence_sfg_delays_and_constants) == str(
            precedence_sfg_registers_and_constants_
        )

        remove(path_)

    def test_load_invalid_path(self):
        path_ = self.get_path(existing=False)
        with pytest.raises(FileNotFoundError):
            python_to_sfg(path_)


class TestGetComponentsOfType:
    def test_get_no_operations_of_type(self, sfg_two_inputs_two_outputs):
        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(
                Multiplication.type_name()
            )
        ] == []

    def test_get_multple_operations_of_type(self, sfg_two_inputs_two_outputs):
        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(
                Addition.type_name()
            )
        ] == ["ADD1", "ADD2"]

        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(
                Input.type_name()
            )
        ] == ["IN1", "IN2"]

        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(
                Output.type_name()
            )
        ] == ["OUT1", "OUT2"]


class TestPrecedenceGraph:
    def test_precedence_graph(self, sfg_simple_filter):
        res = (
            "digraph {\n\trankdir=LR\n\tsubgraph cluster_0"
            " {\n\t\tlabel=N1\n\t\t\"in1.0\" [label=in1]\n\t\t\"t1.0\""
            " [label=t1]\n\t}\n\tsubgraph cluster_1"
            " {\n\t\tlabel=N2\n\t\t\"cmul1.0\" [label=cmul1]\n\t}\n\tsubgraph"
            " cluster_2 {\n\t\tlabel=N3\n\t\t\"add1.0\""
            " [label=add1]\n\t}\n\t\"in1.0\" -> add1\n\tadd1 [label=add1"
            " shape=square]\n\tin1 -> \"in1.0\"\n\tin1 [label=in1"
            " shape=square]\n\t\"t1.0\" -> cmul1\n\tcmul1 [label=cmul1"
            " shape=square]\n\t\"t1.0\" -> out1\n\tout1 [label=out1"
            " shape=square]\n\tt1Out -> \"t1.0\"\n\tt1Out [label=t1"
            " shape=square]\n\t\"cmul1.0\" -> add1\n\tadd1 [label=add1"
            " shape=square]\n\tcmul1 -> \"cmul1.0\"\n\tcmul1 [label=cmul1"
            " shape=square]\n\t\"add1.0\" -> t1In\n\tt1In [label=t1"
            " shape=square]\n\tadd1 -> \"add1.0\"\n\tadd1 [label=add1"
            " shape=square]\n}"
        )

        assert sfg_simple_filter.precedence_graph().source in (res, res + "\n")


class TestSFGGraph:
    def test_sfg(self, sfg_simple_filter):
        res = (
            "digraph {\n\trankdir=LR\n\tin1\n\tin1 -> "
            "add1\n\tout1\n\tt1 -> out1\n\tadd1\n\tcmul1 -> "
            "add1\n\tcmul1\n\tadd1 -> t1\n\tt1 [shape=square]\n\tt1 "
            "-> cmul1\n}"
        )

        assert sfg_simple_filter.sfg().source in (res, res + "\n")

    def test_sfg_show_id(self, sfg_simple_filter):
        res = (
            "digraph {\n\trankdir=LR\n\tin1\n\tin1 -> add1 "
            "[label=s1]\n\tout1\n\tt1 -> out1 [label=s2]\n\tadd1"
            "\n\tcmul1 -> add1 [label=s3]\n\tcmul1\n\tadd1 -> t1 "
            "[label=s4]\n\tt1 [shape=square]\n\tt1 -> cmul1 [label=s5]\n}"
        )

        assert sfg_simple_filter.sfg(show_id=True).source in (res, res + "\n")

    def test_show_sfg_invalid_format(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.show_sfg(format="ppddff")

    def test_show_sfg_invalid_engine(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.show_sfg(engine="ppddff")


class TestSFGErrors:
    def test_dangling_output(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        # No error, maybe should be?
        _ = SFG([in1, in2], [out1])

    def test_unconnected_input_port(self):
        in1 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1)
        out1 = Output(adaptor.output(0))
        with pytest.raises(ValueError, match="Unconnected input port in SFG"):
            SFG([in1], [out1])

    def test_unconnected_output(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        out2 = Output()
        # No error, should be
        SFG([in1, in2], [out1, out2])

    def test_unconnected_input(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        # Correct error?
        with pytest.raises(ValueError, match="Unconnected input port in SFG"):
            SFG([in1, in2], [out1, out2])

    def test_duplicate_input(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        with pytest.raises(ValueError, match="Duplicate input operation"):
            SFG([in1, in1], [out1, out2])

    def test_duplicate_output(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        with pytest.raises(ValueError, match="Duplicate output operation"):
            SFG([in1, in2], [out1, out1])

    def test_unconnected_input_signal(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        signal = Signal()
        with pytest.raises(
            ValueError, match="Input signal #0 is missing destination in SFG"
        ):
            SFG([in1, in2], [out1, out2], [signal])

    def test_unconnected_output_signal(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        signal = Signal()
        with pytest.raises(
            ValueError, match="Output signal #0 is missing source in SFG"
        ):
            SFG([in1, in2], [out1, out2], output_signals=[signal])

    def test_duplicate_input_signal(self):
        in1 = Input()
        signal = Signal()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, signal)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        with pytest.raises(ValueError, match="Duplicate input signal"):
            SFG([in1], [out1, out2], [signal, signal])

    def test_duplicate_output_signal(self):
        in1 = Input()
        in2 = Input()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, in2)
        out1 = Output(adaptor.output(0))
        signal = Signal(adaptor.output(1))
        # Should raise?
        SFG([in1, in2], [out1], output_signals=[signal, signal])
