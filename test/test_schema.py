"""
B-ASIC test suite for the schema module and Schema class.
"""

from b_asic import Schema, Addition, ConstantMultiplication


class TestInit:
    def test_simple_filter_normal_latency(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 4)

        schema = Schema(sfg_simple_filter)

        assert schema._start_times == {"add1": 4, "cmul1": 0}

    def test_complicated_single_outputs_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schema = Schema(precedence_sfg_delays, scheduling_alg="ASAP")

        for op in schema._sfg.get_operations_topological_order():
            print(op.latency_offsets)

        start_times_names = dict()
        for op_id, start_time in schema._start_times.items():
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {"C0": 0, "B1": 0, "B2": 0, "ADD2": 3, "ADD1": 7, "Q1": 11,
                                     "A0": 14, "A1": 0, "A2": 0, "ADD3": 3, "ADD4": 17}

    def test_complicated_single_outputs_complex_latencies(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_offsets_of_type(ConstantMultiplication.type_name(), {'in0': 3, 'out0': 5})

        precedence_sfg_delays.find_by_name("B1")[0].set_latency_offsets({'in0': 4, 'out0': 7})
        precedence_sfg_delays.find_by_name("B2")[0].set_latency_offsets({'in0': 1, 'out0': 4})
        precedence_sfg_delays.find_by_name("ADD2")[0].set_latency_offsets({'in0': 4, 'in1': 2, 'out0': 4})
        precedence_sfg_delays.find_by_name("ADD1")[0].set_latency_offsets({'in0': 1, 'in1': 2, 'out0': 4})
        precedence_sfg_delays.find_by_name("Q1")[0].set_latency_offsets({'in0': 3, 'out0': 6})
        precedence_sfg_delays.find_by_name("A0")[0].set_latency_offsets({'in0': 0, 'out0': 2})

        precedence_sfg_delays.find_by_name("A1")[0].set_latency_offsets({'in0': 0, 'out0': 5})
        precedence_sfg_delays.find_by_name("A2")[0].set_latency_offsets({'in0': 2, 'out0': 3})
        precedence_sfg_delays.find_by_name("ADD3")[0].set_latency_offsets({'in0': 2, 'in1': 1, 'out0': 4})
        precedence_sfg_delays.find_by_name("ADD4")[0].set_latency_offsets({'in0': 6, 'in1': 7, 'out0': 9})

        schema = Schema(precedence_sfg_delays, scheduling_alg="ASAP")

        start_times_names = dict()
        for op_id, start_time in schema._start_times.items():
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {'C0': 0, 'B1': 0, 'B2': 0, 'ADD2': 3, 'ADD1': 5, 'Q1': 6, 'A0': 12,
                                     'A1': 0, 'A2': 0, 'ADD3': 3, 'ADD4': 8}

    def test_independent_sfg(self, sfg_two_inputs_two_outputs_independent_with_cmul):
        schema = Schema(sfg_two_inputs_two_outputs_independent_with_cmul, scheduling_alg="ASAP")

        start_times_names = dict()
        for op_id, start_time in schema._start_times.items():
            op_name = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {'CMUL1': 0, 'CMUL2': 5, "ADD1": 0, "CMUL3": 7}
