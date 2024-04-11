import io
import itertools
import random
import re
import string
import sys
from os import path, remove
from typing import Counter, Dict, Type

import pytest

from b_asic import Input, Output, Signal
from b_asic.core_operations import (
    Addition,
    Butterfly,
    Constant,
    ConstantMultiplication,
    Multiplication,
    SquareRoot,
    Subtraction,
    SymmetricTwoportAdaptor,
)
from b_asic.operation import ResultKey
from b_asic.save_load_structure import python_to_sfg, sfg_to_python
from b_asic.sfg_generators import wdf_allpass
from b_asic.signal_flow_graph import SFG, GraphID
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay


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
            == "id: no_id, \tname: SFG1, \tinputs: {0: '-'}, \toutputs: {0: '-'}\n"
            + "Internal Operations:\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
            + str(sfg.find_by_name("INP1")[0])
            + "\n"
            + str(sfg.find_by_name("INP2")[0])
            + "\n"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg.find_by_name("OUT1")[0])
            + "\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
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
            == "id: no_id, \tname: mac_sfg, \tinputs: {0: '-'}, \toutputs: {0: '-'}\n"
            + "Internal Operations:\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
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
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
        )

    def test_constant(self):
        inp1 = Input("INP1")
        const1 = Constant(3, "CONST")
        add1 = Addition(const1, inp1, "ADD1")
        out1 = Output(add1, "OUT1")

        sfg = SFG(inputs=[inp1], outputs=[out1], name="sfg")

        assert (
            sfg.__str__()
            == "id: no_id, \tname: sfg, \tinputs: {0: '-'}, \toutputs: {0: '-'}\n"
            + "Internal Operations:\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
            + str(sfg.find_by_name("CONST")[0])
            + "\n"
            + str(sfg.find_by_name("INP1")[0])
            + "\n"
            + str(sfg.find_by_name("ADD1")[0])
            + "\n"
            + str(sfg.find_by_name("OUT1")[0])
            + "\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
        )

    def test_simple_filter(self, sfg_simple_filter):
        assert (
            sfg_simple_filter.__str__()
            == "id: no_id, \tname: simple_filter, \tinputs: {0: '-'},"
            " \toutputs: {0: '-'}\n"
            + "Internal Operations:\n"
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
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
            + "--------------------------------------------------------------------"
            + "--------------------------------\n"
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
        with pytest.raises(RuntimeError, match="Direct feedback loop detected"):
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


class TestReplaceOperation:
    def test_replace_addition_by_id(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])
        component_id = "add0"

        sfg = sfg.replace_operation(Multiplication(name="Multi"), graph_id=component_id)
        assert component_id not in sfg._components_by_id.keys()
        assert "Multi" in sfg._components_by_name.keys()

    def test_replace_addition_large_tree(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "add2"

        sfg = sfg.replace_operation(Multiplication(name="Multi"), graph_id=component_id)
        assert "Multi" in sfg._components_by_name.keys()
        assert component_id not in sfg._components_by_id.keys()

    def test_replace_no_input_component(self, operation_tree):
        sfg = SFG(outputs=[Output(operation_tree)])
        component_id = "c0"
        const_ = sfg.find_by_id(component_id)

        sfg = sfg.replace_operation(Constant(1), graph_id=component_id)
        assert const_ is not sfg.find_by_id(component_id)

    def test_no_match_on_replace(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "addd0"

        with pytest.raises(
            ValueError, match="No operation matching the criteria found"
        ):
            sfg = sfg.replace_operation(
                Multiplication(name="Multi"), graph_id=component_id
            )

    def test_not_equal_input(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        component_id = "c0"

        with pytest.raises(
            TypeError,
            match="The input count may not differ between the operations",
        ):
            sfg = sfg.replace_operation(
                Multiplication(name="Multi"), graph_id=component_id
            )


class TestInsertComponent:
    def test_insert_component_in_sfg(self, large_operation_tree_names):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        sqrt = SquareRoot()

        _sfg = sfg.insert_operation(sqrt, sfg.find_by_name("constant4")[0].graph_id)
        assert _sfg.evaluate() != sfg.evaluate()

        assert any([isinstance(comp, SquareRoot) for comp in _sfg.operations])
        assert not any([isinstance(comp, SquareRoot) for comp in sfg.operations])

        assert not isinstance(
            sfg.find_by_name("constant4")[0].output(0).signals[0].destination.operation,
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
        ].destination.operation is sfg.find_by_id("add2")
        assert _sfg.find_by_name("constant4")[0].output(0).signals[
            0
        ].destination.operation is not _sfg.find_by_id("add2")
        assert _sfg.find_by_id("sqrt0").output(0).signals[
            0
        ].destination.operation is _sfg.find_by_id("add2")

    def test_insert_invalid_component_in_sfg(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])

        # Should raise an exception for not matching input count to output count.
        add4 = Addition()
        with pytest.raises(TypeError, match="Source operation output count"):
            sfg.insert_operation(add4, "c0")

    def test_insert_at_output(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])

        # Should raise an exception for trying to insert an operation after an output.
        sqrt = SquareRoot()
        with pytest.raises(TypeError, match="Source operation cannot be an"):
            _ = sfg.insert_operation(sqrt, "out0")

    def test_insert_multiple_output_ports(self, butterfly_operation_tree):
        sfg = SFG(outputs=list(map(Output, butterfly_operation_tree.outputs)))
        _sfg = sfg.insert_operation(Butterfly(name="n_bfly"), "bfly2")

        assert sfg.evaluate() != _sfg.evaluate()

        assert len(sfg.find_by_name("n_bfly")) == 0
        assert len(_sfg.find_by_name("n_bfly")) == 1

        # Correctly connected old output -> new input
        assert (
            _sfg.find_by_name("bfly3")[0].output(0).signals[0].destination.operation
            is _sfg.find_by_name("n_bfly")[0]
        )
        assert (
            _sfg.find_by_name("bfly3")[0].output(1).signals[0].destination.operation
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
            _sfg.find_by_name("n_bfly")[0].output(0).signals[0].destination.operation
            is _sfg.find_by_name("bfly2")[0]
        )
        assert (
            _sfg.find_by_name("n_bfly")[0].output(1).signals[0].destination.operation
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

        assert {comp.name for comp in mac_sfg.find_by_type_name(inp1.type_name())} == {
            "INP1",
            "INP2",
            "INP3",
        }

        assert {comp.name for comp in mac_sfg.find_by_type_name(add1.type_name())} == {
            "ADD1",
            "ADD2",
        }

        assert {comp.name for comp in mac_sfg.find_by_type_name(mul1.type_name())} == {
            "MUL1"
        }

        assert {comp.name for comp in mac_sfg.find_by_type_name(out1.type_name())} == {
            "OUT1"
        }

        assert {
            comp.name for comp in mac_sfg.find_by_type_name(Signal.type_name())
        } == {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}


class TestGetPrecedenceList:
    def test_inputs_delays(self, precedence_sfg_delays):
        # No cached precedence list
        assert precedence_sfg_delays._precedence_list is None

        precedence_list = precedence_sfg_delays.get_precedence_list()

        assert len(precedence_list) == 7

        # Cached precedence list
        assert len(precedence_sfg_delays._precedence_list) == 7

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[0]
        } == {"IN1", "T1", "T2"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[1]
        } == {"C0", "B1", "B2", "A1", "A2"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[2]
        } == {"ADD2", "ADD3"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[3]
        } == {"ADD1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[4]
        } == {"Q1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[5]
        } == {"A0"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[6]
        } == {"ADD4"}

        # Trigger cache
        precedence_list = precedence_sfg_delays.get_precedence_list()

        assert len(precedence_list) == 7

    def test_inputs_constants_delays_multiple_outputs(
        self, precedence_sfg_delays_and_constants
    ):
        precedence_list = precedence_sfg_delays_and_constants.get_precedence_list()

        assert len(precedence_list) == 7

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[0]
        } == {"IN1", "T1", "CONST1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[1]
        } == {"C0", "B1", "B2", "A1", "A2"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[2]
        } == {"ADD2", "ADD3"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[3]
        } == {"ADD1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[4]
        } == {"Q1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[5]
        } == {"A0"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[6]
        } == {"BFLY1.0", "BFLY1.1"}

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

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[0]
        } == {"IN1", "IN2"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[1]
        } == {"CMUL1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[2]
        } == {"NESTED_SFG.0", "NESTED_SFG.1"}

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

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[0]
        } == {"IN1", "IN2"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[1]
        } == {"CMUL1"}

        assert {
            port.operation.key(port.index, port.operation.name)
            for port in precedence_list[2]
        } == {"NESTED_SFG.0", "NESTED_SFG.1"}


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
        assert set(sfg_two_inputs_two_outputs.inputs_required_for_output(0)) == {0, 1}
        assert set(sfg_two_inputs_two_outputs.inputs_required_for_output(1)) == {0, 1}

    def test_depends_sfg_independent(self, sfg_two_inputs_two_outputs_independent):
        assert set(
            sfg_two_inputs_two_outputs_independent.inputs_required_for_output(0)
        ) == {0}
        assert set(
            sfg_two_inputs_two_outputs_independent.inputs_required_for_output(1)
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
        """
        Replaces an SFG with only a operation_tree component with its inner components
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
        """
        Replaces an SFG with only a large_operation_tree component with its inner
        components
        """
        sfg1 = SFG(outputs=[Output(large_operation_tree)])
        out1 = Output(None, "OUT1")
        out1.input(0).connect(sfg1.outputs[0], "S1")
        test_sfg = SFG(outputs=[out1])
        assert test_sfg.evaluate_output(0, []) == 14
        sfg1.connect_external_signals_to_components()
        assert test_sfg.evaluate_output(0, []) == 14
        assert not test_sfg.connect_external_signals_to_components()

    def test_connect_external_signals_to_components_multiple_operations_after_input(
        self,
    ):
        """
        Replaces an SFG with a symmetric two-port adaptor to test when the input
        port goes to multiple operations
        """
        sfg1 = wdf_allpass(0.5)
        sfg2 = sfg1.replace_operation(sfg1.find_by_id('sym2p0').to_sfg(), 'sym2p0')
        sfg2.find_by_id('sfg0').connect_external_signals_to_components()
        test_sfg = SFG(sfg2.input_operations, sfg2.output_operations)
        assert sfg1.evaluate(1) == -0.5
        assert test_sfg.evaluate(1) == -0.5
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
        """Create a simple SFG with either operation_tree or large_operation_tree"""
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

    def test_connect_external_signals_to_components_many_op(self, large_operation_tree):
        """Replace an sfg component in a larger SFG with several component operations"""
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

    def test_add_two_sfgs(self):
        c1 = ConstantMultiplication(0.5)
        c1_sfg = c1.to_sfg()

        c2 = ConstantMultiplication(0.5)
        c2_sfg = c2.to_sfg()

        in1 = Input()
        in2 = Input()

        output = Output(c1_sfg + c2_sfg)
        c1_sfg <<= in1
        c2_sfg <<= in2

        sfg = SFG([in1, in2], [output])
        assert not sfg.find_by_type_name(ConstantMultiplication.type_name())

        c1_sfg.connect_external_signals_to_components()
        sfg = SFG([in1, in2], [output])
        assert len(sfg.find_by_type_name(ConstantMultiplication.type_name())) == 1

        c2_sfg.connect_external_signals_to_components()
        sfg = SFG([in1, in2], [output])
        assert len(sfg.find_by_type_name(ConstantMultiplication.type_name())) == 2


class TestTopologicalOrderOperations:
    def test_feedback_sfg(self, sfg_simple_filter):
        topological_order = sfg_simple_filter.get_operations_topological_order()

        assert [comp.name for comp in topological_order] == [
            "IN1",
            "ADD1",
            "T1",
            "CMUL1",
            "OUT1",
        ]

    def test_multiple_independent_inputs(self, sfg_two_inputs_two_outputs_independent):
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
        topological_order = precedence_sfg_delays.get_operations_topological_order()

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
        new_sfg = sfg_simple_filter.remove_operation("cmul0")

        assert {
            op.name
            for op in sfg_simple_filter.find_by_name("T1")[0].subsequent_operations
        } == {"CMUL1", "OUT1"}
        assert {
            op.name for op in new_sfg.find_by_name("T1")[0].subsequent_operations
        } == {"ADD1", "OUT1"}

        assert {
            op.name
            for op in sfg_simple_filter.find_by_name("ADD1")[0].preceding_operations
        } == {"CMUL1", "IN1"}
        assert {
            op.name for op in new_sfg.find_by_name("ADD1")[0].preceding_operations
        } == {"T1", "IN1"}

        assert "S1" in {
            sig.name
            for sig in sfg_simple_filter.find_by_name("T1")[0].output(0).signals
        }
        assert "S2" in {
            sig.name for sig in new_sfg.find_by_name("T1")[0].output(0).signals
        }

    def test_remove_multiple_inputs_outputs(self, butterfly_operation_tree):
        out1 = Output(butterfly_operation_tree.output(0), "OUT1")
        out2 = Output(butterfly_operation_tree.output(1), "OUT2")

        sfg = SFG(outputs=[out1, out2])

        new_sfg = sfg.remove_operation(sfg.find_by_name("bfly2")[0].graph_id)

        assert sfg.find_by_name("bfly3")[0].output(0).signal_count == 1
        assert new_sfg.find_by_name("bfly3")[0].output(0).signal_count == 1

        sfg_dest_0 = sfg.find_by_name("bfly3")[0].output(0).signals[0].destination
        new_sfg_dest_0 = (
            new_sfg.find_by_name("bfly3")[0].output(0).signals[0].destination
        )

        assert sfg_dest_0.index == 0
        assert new_sfg_dest_0.index == 0
        assert sfg_dest_0.operation.name == "bfly2"
        assert new_sfg_dest_0.operation.name == "bfly1"

        assert sfg.find_by_name("bfly3")[0].output(1).signal_count == 1
        assert new_sfg.find_by_name("bfly3")[0].output(1).signal_count == 1

        sfg_dest_1 = sfg.find_by_name("bfly3")[0].output(1).signals[0].destination
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
        new_sfg_source_0 = new_sfg.find_by_name("bfly1")[0].input(0).signals[0].source

        assert sfg_source_0.index == 0
        assert new_sfg_source_0.index == 0
        assert sfg_source_0.operation.name == "bfly2"
        assert new_sfg_source_0.operation.name == "bfly3"

        sfg_source_1 = sfg.find_by_name("bfly1")[0].input(1).signals[0].source
        new_sfg_source_1 = new_sfg.find_by_name("bfly1")[0].input(1).signals[0].source

        assert sfg_source_1.index == 1
        assert new_sfg_source_1.index == 1
        assert sfg_source_1.operation.name == "bfly2"
        assert new_sfg_source_1.operation.name == "bfly3"

        assert "bfly2" not in {op.name for op in new_sfg.operations}

    def remove_different_number_inputs_outputs(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.remove_operation("add1")


class TestSaveLoadSFG:
    def get_path(self, existing=False):
        path_ = "".join(random.choices(string.ascii_uppercase, k=4)) + ".py"
        while path.exists(path_) if not existing else not path.exists(path_):
            path_ = "".join(random.choices(string.ascii_uppercase, k=4)) + ".py"

        return path_

    def test_save_simple_sfg(self, sfg_simple_filter):
        result = sfg_to_python(sfg_simple_filter)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        with open(path_) as file_obj:
            assert file_obj.read() == result

        remove(path_)

    def test_save_complex_sfg(self, precedence_sfg_delays_and_constants):
        result = sfg_to_python(precedence_sfg_delays_and_constants)
        path_ = self.get_path()

        assert not path.exists(path_)
        with open(path_, "w") as file_obj:
            file_obj.write(result)

        assert path.exists(path_)

        with open(path_) as file_obj:
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

    def test_get_multiple_operations_of_type(self, sfg_two_inputs_two_outputs):
        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(Addition.type_name())
        ] == ["ADD1", "ADD2"]

        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(Input.type_name())
        ] == ["IN1", "IN2"]

        assert [
            op.name
            for op in sfg_two_inputs_two_outputs.find_by_type_name(Output.type_name())
        ] == ["OUT1", "OUT2"]


class TestPrecedenceGraph:
    def test_precedence_graph(self, sfg_simple_filter):
        res = (
            'digraph {\n\trankdir=LR\n\tsubgraph cluster_0 {\n\t\tlabel=N0\n\t\t"in0.0"'
            ' [label=in0 height=0.1 shape=rectangle width=0.1]\n\t\t"t0.0" [label=t0'
            ' height=0.1 shape=rectangle width=0.1]\n\t}\n\tsubgraph cluster_1'
            ' {\n\t\tlabel=N1\n\t\t"cmul0.0" [label=cmul0 height=0.1 shape=rectangle'
            ' width=0.1]\n\t}\n\tsubgraph cluster_2 {\n\t\tlabel=N2\n\t\t"add0.0"'
            ' [label=add0 height=0.1 shape=rectangle width=0.1]\n\t}\n\t"in0.0" ->'
            ' add0\n\tadd0 [label=add0 shape=ellipse]\n\tin0 -> "in0.0"\n\tin0'
            ' [label=in0 shape=cds]\n\t"t0.0" -> cmul0\n\tcmul0 [label=cmul0'
            ' shape=ellipse]\n\t"t0.0" -> out0\n\tout0 [label=out0 shape=cds]\n\tt0Out'
            ' -> "t0.0"\n\tt0Out [label=t0 shape=square]\n\t"cmul0.0" -> add0\n\tadd0'
            ' [label=add0 shape=ellipse]\n\tcmul0 -> "cmul0.0"\n\tcmul0 [label=cmul0'
            ' shape=ellipse]\n\t"add0.0" -> t0In\n\tt0In [label=t0'
            ' shape=square]\n\tadd0 -> "add0.0"\n\tadd0 [label=add0 shape=ellipse]\n}'
        )

        assert sfg_simple_filter.precedence_graph.source in (res, res + "\n")


class TestSFGGraph:
    def test_sfg(self, sfg_simple_filter):
        res = (
            'digraph {\n\trankdir=LR splines=spline\n\tin0 [shape=cds]\n\tin0 -> add0'
            ' [headlabel=0]\n\tout0 [shape=cds]\n\tt0 -> out0\n\tadd0'
            ' [shape=ellipse]\n\tcmul0 -> add0 [headlabel=1]\n\tcmul0'
            ' [shape=ellipse]\n\tadd0 -> t0\n\tt0 [shape=square]\n\tt0 -> cmul0\n}'
        )
        assert sfg_simple_filter.sfg_digraph(branch_node=False).source in (
            res,
            res + "\n",
        )

    def test_sfg_show_id(self, sfg_simple_filter):
        res = (
            'digraph {\n\trankdir=LR splines=spline\n\tin0 [shape=cds]\n\tin0 -> add0'
            ' [label=s0 headlabel=0]\n\tout0 [shape=cds]\n\tt0 -> out0'
            ' [label=s1]\n\tadd0 [shape=ellipse]\n\tcmul0 -> add0 [label=s2'
            ' headlabel=1]\n\tcmul0 [shape=ellipse]\n\tadd0 -> t0 [label=s3]\n\tt0'
            ' [shape=square]\n\tt0 -> cmul0 [label=s4]\n}'
        )

        assert sfg_simple_filter.sfg_digraph(
            show_id=True, branch_node=False
        ).source in (
            res,
            res + "\n",
        )

    def test_sfg_branch(self, sfg_simple_filter):
        res = (
            'digraph {\n\trankdir=LR splines=spline\n\tin0 [shape=cds]\n\tin0 -> add0'
            ' [headlabel=0]\n\tout0 [shape=cds]\n\t"t0.0" -> out0\n\t"t0.0"'
            ' [shape=point]\n\tt0 -> "t0.0" [arrowhead=none]\n\tadd0'
            ' [shape=ellipse]\n\tcmul0 -> add0 [headlabel=1]\n\tcmul0'
            ' [shape=ellipse]\n\tadd0 -> t0\n\tt0 [shape=square]\n\t"t0.0" ->'
            ' cmul0\n}'
        )

        assert sfg_simple_filter.sfg_digraph().source in (
            res,
            res + "\n",
        )

    def test_sfg_no_port_numbering(self, sfg_simple_filter):
        res = (
            'digraph {\n\trankdir=LR splines=spline\n\tin0 [shape=cds]\n\tin0 ->'
            ' add0\n\tout0 [shape=cds]\n\tt0 -> out0\n\tadd0 [shape=ellipse]\n\tcmul0'
            ' -> add0\n\tcmul0 [shape=ellipse]\n\tadd0 -> t0\n\tt0 [shape=square]\n\tt0'
            ' -> cmul0\n}'
        )

        assert sfg_simple_filter.sfg_digraph(
            port_numbering=False, branch_node=False
        ).source in (
            res,
            res + "\n",
        )

    def test_show_sfg_invalid_format(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.show(fmt="ppddff")

    def test_show_sfg_invalid_engine(self, sfg_simple_filter):
        with pytest.raises(ValueError):
            sfg_simple_filter.show(engine="ppddff")


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
        Output(adaptor.output(1))
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

    def test_dangling_input_signal(self):
        in1 = Input()
        signal = Signal()
        adaptor = SymmetricTwoportAdaptor(0.5, in1, signal)
        out1 = Output(adaptor.output(0))
        out2 = Output(adaptor.output(1))
        with pytest.raises(ValueError, match="Dangling signal without source in SFG"):
            SFG([in1], [out1, out2])

    def test_remove_signal_with_different_number_of_inputs_and_outputs(self):
        in1 = Input()
        in2 = Input()
        add1 = Addition(in1, in2, name="addition")
        out1 = Output(add1)
        sfg = SFG([in1, in2], [out1])
        # Try to remove non-existent operation
        sfg1 = sfg.remove_operation("foo")
        assert sfg1 is None
        with pytest.raises(
            ValueError,
            match="Different number of input and output ports of operation with",
        ):
            sfg.remove_operation('add0')

    def test_inputs_required_for_output(self):
        in1 = Input()
        in2 = Input()
        add1 = Addition(in1, in2, name="addition")
        out1 = Output(add1)
        sfg = SFG([in1, in2], [out1])
        with pytest.raises(
            IndexError,
            match=re.escape("Output index out of range (expected 0-0, got 1)"),
        ):
            sfg.inputs_required_for_output(1)


class TestInputDuplicationBug:
    def test_input_is_not_duplicated_in_operation_list(self):
        # Inputs:
        in1 = Input(name="in1")
        out1 = Output(name="out1")

        # Operations:
        t1 = Delay(initial_value=0, name="")
        t1.inputs[0].connect(in1)
        add1 = t1 + in1

        out1.inputs[0].connect(add1)

        twotapfir = SFG(inputs=[in1], outputs=[out1], name='twotapfir')

        assert len([op for op in twotapfir.operations if isinstance(op, Input)]) == 1


class TestCriticalPath:
    def test_single_accumulator(self, sfg_simple_accumulator: SFG):
        sfg_simple_accumulator.set_latency_of_type(Addition.type_name(), 5)
        assert sfg_simple_accumulator.critical_path_time() == 5

        sfg_simple_accumulator.set_latency_of_type(Addition.type_name(), 6)
        assert sfg_simple_accumulator.critical_path_time() == 6


class TestUnfold:
    def count_kinds(self, sfg: SFG) -> Dict[Type, int]:
        return Counter([type(op) for op in sfg.operations])

    # Checks that the number of each kind of operation in sfg2 is multiple*count
    # of the same operation in sfg1.
    # Filters out delay delays
    def assert_counts_is_correct(self, sfg1: SFG, sfg2: SFG, multiple: int):
        count1 = self.count_kinds(sfg1)
        count2 = self.count_kinds(sfg2)

        # Delays should not be duplicated. Check that and then clear them
        # Using get to avoid issues if there are no delays in the sfg
        assert count1.get(Delay) == count2.get(Delay)
        count1[Delay] = 0
        count2[Delay] = 0

        # Ensure that we aren't missing any keys, or have any extras
        assert count1.keys() == count2.keys()

        for k in count1.keys():
            assert count1[k] * multiple == count2[k]

    # This is horrifying, but I can't figure out a way to run the test on multiple
    # fixtures, so this is an ugly hack until someone that knows pytest comes along
    def test_two_inputs_two_outputs(self, sfg_two_inputs_two_outputs: SFG):
        self.do_tests(sfg_two_inputs_two_outputs)

    def test_twotapfir(self, sfg_two_tap_fir: SFG):
        self.do_tests(sfg_two_tap_fir)

    def test_delay(self, sfg_delay: SFG):
        self.do_tests(sfg_delay)

    def test_sfg_two_inputs_two_outputs_independent(
        self, sfg_two_inputs_two_outputs_independent: SFG
    ):
        self.do_tests(sfg_two_inputs_two_outputs_independent)

    def test_threetapiir(self, sfg_direct_form_iir_lp_filter: SFG):
        self.do_tests(sfg_direct_form_iir_lp_filter)

    def do_tests(self, sfg: SFG):
        for factor in range(2, 4):
            # Ensure that the correct number of operations get created
            unfolded = sfg.unfold(factor)

            self.assert_counts_is_correct(sfg, unfolded, factor)

            double_unfolded = sfg.unfold(factor).unfold(factor)

            self.assert_counts_is_correct(sfg, double_unfolded, factor * factor)

            NUM_TESTS = 5
            # Evaluate with some random values
            # To avoid problems with missing inputs at the end of the sequence,
            # we generate i*(some large enough) number
            input_list = [
                [random.random() for _ in range(0, NUM_TESTS * factor)]
                for _ in sfg.inputs
            ]

            sim = Simulation(sfg, input_list)
            sim.run()
            ref = sim.results

            # We have i copies of the inputs, each sourcing their input from the orig
            unfolded_input_lists = [[] for _ in range(len(sfg.inputs) * factor)]
            for t in range(0, NUM_TESTS):
                for n in range(0, factor):
                    for k in range(0, len(sfg.inputs)):
                        unfolded_input_lists[k + n * len(sfg.inputs)].append(
                            input_list[k][t * factor + n]
                        )

            sim = Simulation(unfolded, unfolded_input_lists)
            sim.run()
            unfolded_results = sim.results

            for n, _ in enumerate(sfg.outputs):
                # Outputs for an original output
                ref_values = list(ref[ResultKey(f"{n}")])

                # Output n will be split into `factor` output ports, compute the
                # indices where we find the outputs
                out_indices = [n + k * len(sfg.outputs) for k in range(factor)]
                u_values = [
                    [unfolded_results[ResultKey(f"{idx}")][k] for idx in out_indices]
                    for k in range(int(NUM_TESTS))
                ]

                flat_u_values = list(itertools.chain.from_iterable(u_values))

                assert flat_u_values == ref_values

    def test_value_error(self, sfg_two_inputs_two_outputs: SFG):
        sfg = sfg_two_inputs_two_outputs
        with pytest.raises(ValueError, match="Unfolding 0 times removes the SFG"):
            sfg.unfold(0)


class TestIsLinear:
    def test_single_accumulator(self, sfg_simple_accumulator: SFG):
        assert sfg_simple_accumulator.is_linear

    def test_sfg_nested(self, sfg_nested: SFG):
        assert not sfg_nested.is_linear


class TestIsConstant:
    def test_single_accumulator(self, sfg_simple_accumulator: SFG):
        assert not sfg_simple_accumulator.is_constant

    def test_sfg_nested(self, sfg_nested: SFG):
        assert not sfg_nested.is_constant


class TestSwapIOOfOperation:
    def do_test(self, sfg: SFG, graph_id: GraphID):
        NUM_TESTS = 5
        # Evaluate with some random values
        # To avoid problems with missing inputs at the end of the sequence,
        # we generate i*(some large enough) number
        input_list = [
            [random.random() for _ in range(0, NUM_TESTS)] for _ in sfg.inputs
        ]
        sim_ref = Simulation(sfg, input_list)
        sim_ref.run()

        sfg.swap_io_of_operation(graph_id)
        sim_swap = Simulation(sfg, input_list)
        sim_swap.run()
        for n, _ in enumerate(sfg.outputs):
            ref_values = list(sim_ref.results[ResultKey(f"{n}")])
            swap_values = list(sim_swap.results[ResultKey(f"{n}")])
            assert ref_values == swap_values

    def test_single_accumulator(self, sfg_simple_accumulator: SFG):
        self.do_test(sfg_simple_accumulator, 'add1')


class TestInsertComponentAfter:
    def test_insert_component_after_in_sfg(self, large_operation_tree_names):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        sqrt = SquareRoot()

        _sfg = sfg.insert_operation_after(
            sfg.find_by_name("constant4")[0].graph_id, sqrt
        )
        assert _sfg.evaluate() != sfg.evaluate()

        assert any([isinstance(comp, SquareRoot) for comp in _sfg.operations])
        assert not any([isinstance(comp, SquareRoot) for comp in sfg.operations])

        assert not isinstance(
            sfg.find_by_name("constant4")[0].output(0).signals[0].destination.operation,
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
        ].destination.operation is sfg.find_by_id("add2")
        assert _sfg.find_by_name("constant4")[0].output(0).signals[
            0
        ].destination.operation is not _sfg.find_by_id("add2")
        assert _sfg.find_by_id("sqrt0").output(0).signals[
            0
        ].destination.operation is _sfg.find_by_id("add2")

    def test_insert_component_after_mimo_operation_error(
        self, large_operation_tree_names
    ):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        with pytest.raises(
            TypeError, match="Only operations with one input and one output"
        ):
            sfg.insert_operation_after('constant4', SymmetricTwoportAdaptor(0.5))

    def test_insert_component_after_unknown_component_error(
        self, large_operation_tree_names
    ):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        with pytest.raises(ValueError, match="Unknown component:"):
            sfg.insert_operation_after('foo', SquareRoot())


class TestInsertComponentBefore:
    def test_insert_component_before_in_sfg(self, butterfly_operation_tree):
        sfg = SFG(outputs=list(map(Output, butterfly_operation_tree.outputs)))
        sqrt = SquareRoot()

        _sfg = sfg.insert_operation_before(
            sfg.find_by_name("bfly1")[0].graph_id, sqrt, port=0
        )
        assert _sfg.evaluate() != sfg.evaluate()

        assert any([isinstance(comp, SquareRoot) for comp in _sfg.operations])
        assert not any([isinstance(comp, SquareRoot) for comp in sfg.operations])

        assert not isinstance(
            sfg.find_by_name("bfly1")[0].input(0).signals[0].source.operation,
            SquareRoot,
        )
        assert isinstance(
            _sfg.find_by_name("bfly1")[0].input(0).signals[0].source.operation,
            SquareRoot,
        )

        assert (
            sfg.find_by_name("bfly1")[0].input(0).signals[0].source.operation
            is sfg.find_by_name("bfly2")[0]
        )
        assert (
            _sfg.find_by_name("bfly1")[0].input(0).signals[0].destination.operation
            is not _sfg.find_by_name("bfly2")[0]
        )
        assert (
            _sfg.find_by_id("sqrt0").input(0).signals[0].source.operation
            is _sfg.find_by_name("bfly2")[0]
        )

    def test_insert_component_before_mimo_operation_error(
        self, large_operation_tree_names
    ):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        with pytest.raises(
            TypeError, match="Only operations with one input and one output"
        ):
            sfg.insert_operation_before('add0', SymmetricTwoportAdaptor(0.5), port=0)

    def test_insert_component_before_unknown_component_error(
        self, large_operation_tree_names
    ):
        sfg = SFG(outputs=[Output(large_operation_tree_names)])
        with pytest.raises(ValueError, match="Unknown component:"):
            sfg.insert_operation_before('foo', SquareRoot())


class TestGetUsedTypeNames:
    def test_single_accumulator(self, sfg_simple_accumulator: SFG):
        assert sfg_simple_accumulator.get_used_type_names() == ['add', 'in', 'out', 't']

    def test_sfg_nested(self, sfg_nested: SFG):
        assert sfg_nested.get_used_type_names() == ['in', 'out', 'sfg']

    def test_large_operation_tree(self, large_operation_tree):
        sfg = SFG(outputs=[Output(large_operation_tree)])
        assert sfg.get_used_type_names() == ['add', 'c', 'out']


class TestInsertDelays:
    def test_insert_delays_before_operation(self):
        in1 = Input()
        bfly = Butterfly()
        d1 = bfly.input(0).delay(2)
        d2 = bfly.input(1).delay(1)
        d1 <<= in1
        d2 <<= in1
        out1 = Output(bfly.output(0))
        out2 = Output(bfly.output(1))
        sfg = SFG([in1], [out1, out2])

        d_type_name = d1.operation.type_name()

        assert len(sfg.find_by_type_name(d_type_name)) == 3

        sfg.find_by_id('out1').input(0).delay(3)
        sfg = sfg()

        assert len(sfg.find_by_type_name(d_type_name)) == 6
        source1 = sfg.find_by_id('out1').input(0).signals[0].source.operation
        source2 = source1.input(0).signals[0].source.operation
        source3 = source2.input(0).signals[0].source.operation
        source4 = source3.input(0).signals[0].source.operation
        assert source1.type_name() == d_type_name
        assert source2.type_name() == d_type_name
        assert source3.type_name() == d_type_name
        assert source4.type_name() == bfly.type_name()
