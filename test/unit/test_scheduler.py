import pulp
import pytest

import b_asic.scheduler as scheduler_module
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.fft_operations import R2Butterfly
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler, ILPScheduler
from b_asic.sfg import SFG
from b_asic.sfg_generators import direct_form_1_iir, radix_2_dif_fft
from b_asic.special_operations import Input, Output


class TestASAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match=r"Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ASAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ASAPScheduler())

        assert schedule.start_times == {
            "in0": 0,
            "cmul0": 0,
            "cmul1": 0,
            "cmul2": 0,
            "cmul3": 0,
            "cmul4": 0,
            "add3": 2,
            "add1": 2,
            "add0": 5,
            "add2": 8,
            "out0": 11,
        }
        assert schedule.schedule_time == 11

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler())

        assert schedule.start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul2": 0,
            "cmul3": 0,
            "add3": 4,
            "add1": 4,
            "add0": 9,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 23

    def test_direct_form_2_iir_with_scheduling_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler(), schedule_time=30
        )

        assert schedule.start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul2": 0,
            "cmul3": 0,
            "add3": 4,
            "add1": 4,
            "add0": 9,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 30

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(R2Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(R2Butterfly.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ASAPScheduler())

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "r2bfly0": 0,
            "r2bfly6": 0,
            "r2bfly8": 0,
            "r2bfly11": 0,
            "cmul3": 1,
            "r2bfly7": 1,
            "cmul2": 1,
            "r2bfly1": 1,
            "cmul0": 1,
            "cmul4": 2,
            "r2bfly9": 2,
            "r2bfly5": 3,
            "r2bfly2": 3,
            "out0": 3,
            "out4": 3,
            "r2bfly10": 4,
            "cmul1": 4,
            "r2bfly3": 4,
            "out1": 5,
            "out2": 5,
            "out5": 5,
            "out6": 5,
            "r2bfly4": 6,
            "out3": 7,
            "out7": 7,
        }
        assert schedule.schedule_time == 7


class TestALAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match=r"Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ALAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "cmul3": 0,
            "cmul4": 0,
            "add1": 2,
            "in0": 3,
            "cmul0": 3,
            "cmul1": 3,
            "cmul2": 3,
            "add3": 5,
            "add0": 5,
            "add2": 8,
            "out0": 11,
        }
        assert schedule.schedule_time == 11

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "cmul3": 0,
            "cmul4": 0,
            "add1": 4,
            "in0": 9,
            "cmul2": 9,
            "cmul1": 9,
            "add0": 9,
            "add3": 13,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 23

    def test_direct_form_2_iir_with_scheduling_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, scheduler=ALAPScheduler(), schedule_time=30
        )

        assert schedule.start_times == {
            "cmul3": 7,
            "cmul4": 7,
            "add1": 11,
            "in0": 16,
            "cmul2": 16,
            "cmul1": 16,
            "add0": 16,
            "add3": 20,
            "cmul0": 21,
            "add2": 25,
            "out0": 30,
        }
        assert schedule.schedule_time == 30

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(R2Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(R2Butterfly.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "in3": 0,
            "in7": 0,
            "in1": 0,
            "in5": 0,
            "r2bfly6": 0,
            "r2bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "in2": 2,
            "in6": 2,
            "r2bfly11": 2,
            "r2bfly7": 3,
            "cmul0": 3,
            "r2bfly5": 3,
            "in0": 4,
            "in4": 4,
            "cmul4": 4,
            "cmul1": 4,
            "r2bfly0": 4,
            "r2bfly1": 5,
            "r2bfly2": 5,
            "r2bfly9": 6,
            "r2bfly10": 6,
            "r2bfly3": 6,
            "r2bfly4": 6,
            "out0": 7,
            "out1": 7,
            "out2": 7,
            "out3": 7,
            "out4": 7,
            "out5": 7,
            "out6": 7,
            "out7": 7,
        }
        assert schedule.schedule_time == 7


class TestILPScheduler:
    def test_output_placement_once_per_bound_calculation(self, monkeypatch):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=1, execution_time=1)
            for value in (2, 3)
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        placements = []
        place_outputs = scheduler_module.Scheduler._place_outputs_on_given_times

        def track_output_placement(scheduler):
            placements.append(type(scheduler))
            place_outputs(scheduler)

        monkeypatch.setattr(
            scheduler_module.Scheduler,
            "_place_outputs_on_given_times",
            track_output_placement,
        )
        Schedule(
            sfg,
            ILPScheduler(output_delta_times={"out0": 0, "out1": 1}),
            schedule_time=5,
        )
        assert placements == [ASAPScheduler, ASAPScheduler]

    @pytest.mark.parametrize("execution_time", [1, 11])
    @pytest.mark.parametrize("cyclic", [False, True])
    @pytest.mark.parametrize("complete", [False, True])
    @pytest.mark.parametrize(
        "timing_kind", ["input_times", "output_times", "output_delta_times"]
    )
    def test_io_resource_bounds_from_timing_constraints(
        self, monkeypatch, cyclic, complete, timing_kind, execution_time
    ):
        inputs = [Input() for _ in range(3)]
        multiplications = [
            ConstantMultiplication(value, input_op, latency=1, execution_time=1)
            for value, input_op in enumerate(inputs, start=2)
        ]
        sfg = SFG(inputs=inputs, outputs=[Output(op) for op in multiplications])
        is_input = timing_kind == "input_times"
        prefix = "in" if is_input else "out"
        first_time = 5 if timing_kind == "output_times" else 0
        timings = {f"{prefix}0": first_time, f"{prefix}1": first_time}
        if complete:
            timings[f"{prefix}2"] = first_time + 1
        solve = scheduler_module._solve_ilp_problem
        bounds = []
        sfg.set_execution_time_of_type(Input if is_input else Output, execution_time)

        def check_resource_bounds(problem, solver, *, warm_start):
            resource = problem.variablesDict()[f"R_used_{prefix}"]
            bounds.append((resource.lowBound, resource.upBound))
            return solve(problem, solver, warm_start=warm_start)

        monkeypatch.setattr(
            scheduler_module, "_solve_ilp_problem", check_resource_bounds
        )
        Schedule(
            sfg,
            ILPScheduler(**{timing_kind: timings}),
            schedule_time=10,
            cyclic=cyclic,
        )
        required = 2
        if execution_time > 1:
            required = (4 if cyclic else 2) + int(complete)
        assert bounds == [(required, required if complete else float("inf"))]

    def test_warm_start_shifts_unspecified_outputs_with_output_group(self, monkeypatch):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=latency, execution_time=1)
            for value, latency in ((2, 3), (3, 3), (4, 1))
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        solve = scheduler_module._solve_ilp_problem
        candidates = []

        def check_initial_solution(problem, solver, *, warm_start):
            candidates.append(warm_start)
            assert warm_start
            assert problem.valid()
            assert pulp.value(problem.variablesDict()["output_origin"]) == 9
            assert pulp.value(problem.variablesDict()["R_used_out"]) == 1
            return solve(problem, solver, warm_start=warm_start)

        monkeypatch.setattr(
            scheduler_module, "_solve_ilp_problem", check_initial_solution
        )
        Schedule(
            sfg,
            ILPScheduler(
                input_times={"in0": 0},
                output_delta_times={"out0": 0, "out1": 1},
            ),
            schedule_time=10,
        )
        assert candidates == [True]

    @pytest.mark.parametrize("cyclic", [False, True])
    @pytest.mark.parametrize("fixed_output_time", [None, 3])
    def test_asap_warm_start_only_when_feasible(
        self, monkeypatch, cyclic, fixed_output_time
    ):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=1, execution_time=7)
            for value in (2, 3)
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        solver = pulp.HiGHS(msg=False)
        solve = scheduler_module._solve_ilp_problem
        candidates = []

        def check_initial_solution(problem, solver, *, warm_start):
            candidates.append(warm_start)
            if warm_start:
                assert problem.valid()
                assert pulp.value(problem.variablesDict()["R_used_cmul"]) == (
                    4 if cyclic else 2
                )
                assert pulp.value(problem.variablesDict()["output_origin"]) == (
                    1 if cyclic else 4
                )
            return solve(problem, solver, warm_start=warm_start)

        monkeypatch.setattr(
            scheduler_module, "_solve_ilp_problem", check_initial_solution
        )
        schedule = Schedule(
            sfg,
            ILPScheduler(
                solver=solver,
                input_times={"in0": 0},
                output_delta_times={"out0": 0, "out1": 1},
                output_times=(
                    {"out0": fixed_output_time}
                    if fixed_output_time is not None
                    else None
                ),
            ),
            schedule_time=5,
            cyclic=cyclic,
        )
        assert candidates == [fixed_output_time is None]
        assert solver.optionsDict.get("warmStart", False) == (fixed_output_time is None)
        if fixed_output_time is not None:
            assert schedule.start_times["out0"] == fixed_output_time

    @pytest.mark.parametrize("cyclic", [False, True])
    @pytest.mark.parametrize("execution_time", [1, 2, 7])
    def test_resource_occupancy_at_period_boundary(
        self, monkeypatch, cyclic, execution_time
    ):
        inputs = [Input(), Input()]
        multiplications = [
            ConstantMultiplication(
                2, input_op, latency=1, execution_time=execution_time
            )
            for input_op in inputs
        ]
        sfg = SFG(inputs=inputs, outputs=[Output(op) for op in multiplications])
        problems = []
        solve = scheduler_module._solve_ilp_problem

        def capture_problem(problem, solver, **kwargs):
            problems.append(problem)
            return solve(problem, solver, **kwargs)

        monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", capture_problem)
        schedule = Schedule(
            sfg,
            ILPScheduler(
                input_times={"in0": 0, "in1": 4},
                output_times={"out0": 1, "out1": 0},
            ),
            schedule_time=5,
            cyclic=cyclic,
        )
        # The deadlines force starts at 0 and 4. Check the resource count
        # optimized by the ILP, including executions longer than one period.
        counts = [0] * (5 if cyclic else 4 + execution_time)
        for start in (0, 4):
            for offset in range(execution_time):
                time = (start + offset) % 5 if cyclic else start + offset
                counts[time] += 1
        resources = problems[0].variablesDict()["R_used_cmul"]
        assert pulp.value(resources) == max(counts)
        assert sorted(
            schedule.start_times[op.graph_id]
            for op in schedule.sfg.find_by_type(ConstantMultiplication)
        ) == [0, 4]

    @pytest.mark.parametrize(("schedule_time", "expected_resources"), [(3, 2), (10, 1)])
    def test_relative_output_times_allow_resource_sharing(
        self, schedule_time, expected_resources
    ):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=2, execution_time=1)
            for value in range(2, 6)
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        deltas = {"out0": 0, "out1": 0, "out2": 1, "out3": 1}
        schedule = Schedule(
            sfg,
            ILPScheduler(input_times={"in0": 0}, output_delta_times=deltas),
            schedule_time=schedule_time,
        )
        origin = schedule.start_times["out0"]
        assert {key: schedule.start_times[key] - origin for key in deltas} == deltas
        assert max(schedule.start_times.values()) <= schedule_time
        assert (
            schedule.get_operations()
            .get_by_type_name("cmul")
            .processing_element_bound()
            == expected_resources
        )

    def test_resource_occupancy_across_multiple_periods(self, monkeypatch):
        inputs = [Input(), Input()]
        multiplications = [
            ConstantMultiplication(2, inputs[0], latency=5, execution_time=1),
            ConstantMultiplication(3, inputs[1], latency=1, execution_time=1),
        ]
        sfg = SFG(inputs=inputs, outputs=[Output(op) for op in multiplications])
        problems = []
        solve = scheduler_module._solve_ilp_problem

        def capture_problem(problem, solver, **kwargs):
            problems.append(problem)
            return solve(problem, solver, **kwargs)

        monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", capture_problem)
        schedule = Schedule(
            sfg,
            ILPScheduler(
                input_times={"in0": 0, "in1": 5},
                output_times={"out0": 0, "out1": 1},
                max_time=7,
            ),
            schedule_time=5,
            cyclic=True,
        )
        # The unwrapped starts are forced to 0 and 5. Even with execution
        # time 1, these compete for the same slot in a periodic schedule.
        assert pulp.value(problems[0].variablesDict()["R_used_cmul"]) == 2
        assert (
            schedule.get_operations()
            .get_by_type_name("cmul")
            .processing_element_bound()
            == 2
        )

    @pytest.mark.parametrize("schedule_time", [5, 60])
    def test_fold_schedule_with_operation_crossing_period(self, schedule_time):
        input_op = Input()
        first = ConstantMultiplication(2, input_op, latency=2, execution_time=1)
        second = ConstantMultiplication(3, first, latency=1, execution_time=1)
        sfg = SFG(inputs=[input_op], outputs=[Output(second)])

        schedule = Schedule(
            sfg,
            ILPScheduler(
                input_times={"in0": schedule_time - 1},
                output_times={"out0": 2},
                output_delta_times={"out0": 0},
                max_time=2 * schedule_time,
            ),
            schedule_time=schedule_time,
            cyclic=True,
        )

        assert schedule.schedule_time == schedule_time
        assert schedule.start_times == {
            "in0": schedule_time - 1,
            "cmul0": schedule_time - 1,
            "cmul1": 1,
            "out0": 2,
        }
        assert schedule.get_max_end_time() == schedule_time + 1
        assert all(lap == 0 for lap in schedule.laps.values())
        for graph_id in schedule.start_times:
            assert schedule.backward_slack(graph_id) >= 0
            assert schedule.forward_slack(graph_id) >= 0
        assert schedule.forward_slack("cmul0") == 0
        assert schedule.forward_slack("cmul1") == 0

    @pytest.mark.parametrize("max_time", [None, 10, 20])
    def test_relative_output_upper_bounds_use_available_horizon(self, max_time):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=2, execution_time=1)
            for value in range(2, 5)
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        schedule = Schedule(sfg, schedule_time=10)
        scheduler = ILPScheduler()
        upper_bounds = scheduler._get_alap_start_times(
            schedule,
            input_times={"in0": 0},
            output_delta_times={"out0": 0, "out1": 1},
            max_time=max_time,
        )
        horizon = max_time or 10
        assert upper_bounds["in0"] == 0
        assert upper_bounds["out0"] == horizon - 1
        assert upper_bounds["out1"] == horizon
        assert upper_bounds["out2"] == horizon
        assert upper_bounds["cmul0"] == horizon - 3
        assert upper_bounds["cmul1"] == horizon - 2
        assert max(upper_bounds.values()) <= horizon

    def test_relative_output_times_contribute_to_asap_schedule_time(self):
        input_op = Input()
        multiplications = [
            ConstantMultiplication(value, input_op, latency=2, execution_time=1)
            for value in (2, 3)
        ]
        sfg = SFG(inputs=[input_op], outputs=[Output(op) for op in multiplications])
        with pytest.raises(ValueError, match=r"Shortest possible schedule time, 5"):
            Schedule(
                sfg,
                ILPScheduler(output_delta_times={"out0": 0, "out1": 3}),
                schedule_time=4,
            )

    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match=r"Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ALAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        schedule = Schedule(sfg, ILPScheduler(), schedule_time=11)

        assert schedule.schedule_time == 11

        schedule = Schedule(sfg, ILPScheduler(), schedule_time=50)
        assert schedule.schedule_time == 50

        ops = schedule.get_operations()
        assert ops.get_by_type_name("add").processing_element_bound() == 1
        assert ops.get_by_type_name("cmul").processing_element_bound() == 1
        assert ops.get_by_type_name("in").processing_element_bound() == 1
        assert ops.get_by_type_name("out").processing_element_bound() == 1

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition, 2)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(ConstantMultiplication, 3)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            ConstantMultiplication, 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(Addition, 1)

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, ILPScheduler(), schedule_time=15
        )
        assert schedule.schedule_time == 15

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, ILPScheduler(), schedule_time=60
        )
        assert schedule.schedule_time == 60

        ops = schedule.get_operations()
        assert ops.get_by_type_name("add").processing_element_bound() == 1
        assert ops.get_by_type_name("cmul").processing_element_bound() == 1
        assert ops.get_by_type_name("in").processing_element_bound() == 1
        assert ops.get_by_type_name("out").processing_element_bound() == 1
