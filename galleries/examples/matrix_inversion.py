"""
================
Matrix Inversion
================

In this example, the process of deriving a time-multiplexed architecture
for matrix inversion is demonstrated.
"""

# %%
# Create a signal-flow-graph (SFG) using a provided generator

from b_asic.sfg_generators.matrix_inversion import ldlt_matrix_inverse


sfg = ldlt_matrix_inverse(
    N=4,
    mode="mult",
    pe="addsub",
)

# %%
# Display the number of operations in the SFG

sfg.operation_counter()

# %%
# Display the SFG

sfg.display()

# %%
# Schedule the operations from the SFG using a list-based scheduling heuristic
# Use 2 addsub PEs, 2 mul PEs, 1 reciprocal PE, 1 negation PE, 1 input port, and 1 output port

from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule

sfg.set_latency_of_type_name("addsub", 9)
sfg.set_latency_of_type_name("mul", 6)
sfg.set_latency_of_type_name("rec", 19)
sfg.set_latency_of_type_name("neg", 1)

sfg.set_execution_time_of_type_name("addsub", 1)
sfg.set_execution_time_of_type_name("mul", 1)
sfg.set_execution_time_of_type_name("rec", 1)
sfg.set_execution_time_of_type_name("neg", 1)

resources = {
    "addsub": 1,
    "mul": 1,
    "rec": 1,
    "neg": 1,
    "in": 1,
    "out": 1,
}

scheduler = HybridScheduler(max_resources=resources)
schedule = Schedule(sfg, scheduler=scheduler)
print(schedule.schedule_time)

# %%
# Derive an architecture with the minimal amount of PEs, memories, and minimal mux complexity

from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.architecture import Architecture

pes, mems, direct = assign_processing_elements_and_memories(
    schedule,
    strategy="ilp_min_mux",
    memory_read_ports=1,
    memory_write_ports=1,
    memory_total_ports=2,
    memory_type="RAM",
    max_mux_size=4, # set the maximum number of multiplexer inputs
)

arch = Architecture(pes, mems, "matinv", direct)
arch

# %%
# Generate VHDL code, targeting single-precision floating-point arithmetic
# and using AMD Floating-Point IP cores.
# Some additional options are specified to demonstrate the configurability
# the code generation.

from b_asic.code_printer import VhdlPrinter
from b_asic.data_type import DataType, NumRepresentation

dt = DataType(
    wl=(8, 23),
    num_repr=NumRepresentation.FLOATING_POINT,
)

printer = VhdlPrinter(dt)
printer.print(
    arch,
    path="generated",
    pe_registers = { # only generate 2 pipeline stages, the rest are inside the used IP
        "addsub": (1, 1),
        "mul": (1, 1),
        "rec": (1, 1),
    },
    fp_backend={ # specify backend for each floating-point operation
        "addsub0": "amd",
        "mul0": "amd",
        "rec0": "amd",
    },
    io_registers=True, # add registers to input and output ports
    multiplexer_control_registered = True, # pipeline mux control signals
    pipeline_pe_control = True, # pipeline processing element control signals
    pipeline_mem_control = True, # pipeline memory control signals
)

# %%
# The VHDL code has been generated in the "generated" directory, with the PEs containing instantiated
# AMD Floating-Point IP cores.

# %%
