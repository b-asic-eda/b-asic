# -*- coding: utf-8 -*-
from qtpy.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from b_asic.signal_generator import (
    Constant,
    FromFile,
    Gaussian,
    Impulse,
    SignalGenerator,
    Sinusoid,
    Step,
    Uniform,
    ZeroPad,
)


class SignalGeneratorInput(QGridLayout):
    """Abstract class for graphically configuring and generating signal generators."""

    def __init__(self, logger, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logger

    def get_generator(self) -> SignalGenerator:
        """Return the SignalGenerator based on the graphical input."""
        raise NotImplementedError


class DelayInput(SignalGeneratorInput):
    """
    Abstract class for graphically configuring and generating signal generators that
    have a single delay parameter.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay_label = QLabel("Delay")
        self.addWidget(self.delay_label, 0, 0)
        self.delay_spin_box = QSpinBox()
        self.delay_spin_box.setRange(0, 2147483647)
        self.addWidget(self.delay_spin_box, 0, 1)

    def get_generator(self) -> SignalGenerator:
        raise NotImplementedError


class ImpulseInput(DelayInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Impulse` signal generator.
    """

    def get_generator(self) -> SignalGenerator:
        return Impulse(self.delay_spin_box.value())


class StepInput(DelayInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Step` signal generator.
    """

    def get_generator(self) -> SignalGenerator:
        return Step(self.delay_spin_box.value())


class ZeroPadInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.ZeroPad` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_label = QLabel("Input")
        self.addWidget(self.input_label, 0, 0)
        self.input_sequence = QLineEdit()
        self.addWidget(self.input_sequence, 0, 1)

    def get_generator(self) -> SignalGenerator:
        input_values = []
        for val in self.input_sequence.text().split(","):
            val = val.strip()
            try:
                if not val:
                    val = 0

                val = complex(val)
            except ValueError:
                self._logger.warning(f"Skipping value: {val}, not a digit.")
                continue

            input_values.append(val)

        return ZeroPad(input_values)


class FromFileInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.FromFile` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_label = QLabel("Browse")
        self.addWidget(self.file_label, 0, 0)
        self.file_browser = QPushButton("No file selected")
        self.file_browser.clicked.connect(
            lambda i: self.get_input_file(i, self.file_browser)
        )
        self.addWidget(self.file_browser, 0, 1)

    def get_generator(self) -> SignalGenerator:
        return FromFile(self.file_browser.text())

    def get_input_file(self, i, file_browser):
        module, accepted = QFileDialog().getOpenFileName()
        file_browser.setText(module)
        return


class SinusoidInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Sinusoid` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frequency_label = QLabel("Frequency")
        self.addWidget(self.frequency_label, 0, 0)
        self.frequency_input = QLineEdit()
        self.addWidget(self.frequency_input, 0, 1)

        self.phase_label = QLabel("Phase")
        self.addWidget(self.phase_label, 1, 0)
        self.phase_input = QLineEdit()
        self.addWidget(self.phase_input, 1, 1)

    def get_generator(self) -> SignalGenerator:
        frequency = self.frequency_input.text().strip()
        try:
            if not frequency:
                frequency = 0.1

            frequency = float(frequency)
        except ValueError:
            self._logger.warning(f"Cannot parse frequency: {frequency} not a number.")
            frequency = 0.1

        phase = self.phase_input.text().strip()
        try:
            if not phase:
                phase = 0

            phase = float(phase)
        except ValueError:
            self._logger.warning(f"Cannot parse phase: {phase} not a number.")
            phase = 0

        return Sinusoid(frequency, phase)


class GaussianInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Gaussian` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scale_label = QLabel("Standard deviation")
        self.addWidget(self.scale_label, 0, 0)
        self.scale_input = QLineEdit()
        self.scale_input.setText("1.0")
        self.addWidget(self.scale_input, 0, 1)

        self.loc_label = QLabel("Average value")
        self.addWidget(self.loc_label, 1, 0)
        self.loc_input = QLineEdit()
        self.loc_input.setText("0.0")
        self.addWidget(self.loc_input, 1, 1)

        self.seed_label = QLabel("Seed")
        self.addWidget(self.seed_label, 2, 0)
        self.seed_spin_box = QSpinBox()
        self.seed_spin_box.setRange(0, 2147483647)
        self.addWidget(self.seed_spin_box, 2, 1)

    def get_generator(self) -> SignalGenerator:
        scale = self.scale_input.text().strip()
        try:
            if not scale:
                scale = 1

            scale = float(scale)
        except ValueError:
            self._logger.warning(f"Cannot parse scale: {scale} not a number.")
            scale = 1

        loc = self.loc_input.text().strip()
        try:
            if not loc:
                loc = 0

            loc = float(loc)
        except ValueError:
            self._logger.warning(f"Cannot parse loc: {loc} not a number.")
            loc = 0

        return Gaussian(self.seed_spin_box.value(), loc, scale)


class UniformInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Uniform` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.low_label = QLabel("Lower bound")
        self.addWidget(self.low_label, 0, 0)
        self.low_input = QLineEdit()
        self.low_input.setText("-1.0")
        self.addWidget(self.low_input, 0, 1)

        self.high_label = QLabel("Upper bound")
        self.addWidget(self.high_label, 1, 0)
        self.high_input = QLineEdit()
        self.high_input.setText("1.0")
        self.addWidget(self.high_input, 1, 1)

        self.seed_label = QLabel("Seed")
        self.addWidget(self.seed_label, 2, 0)
        self.seed_spin_box = QSpinBox()
        self.seed_spin_box.setRange(0, 2147483647)
        self.addWidget(self.seed_spin_box, 2, 1)

    def get_generator(self) -> SignalGenerator:
        low = self.low_input.text().strip()
        try:
            if not low:
                low = -1.0

            low = float(low)
        except ValueError:
            self._logger.warning(f"Cannot parse low: {low} not a number.")
            low = -1.0

        high = self.high_input.text().strip()
        try:
            if not high:
                high = 1.0

            high = float(high)
        except ValueError:
            self._logger.warning(f"Cannot parse high: {high} not a number.")
            high = 1.0

        return Uniform(self.seed_spin_box.value(), low, high)


class ConstantInput(SignalGeneratorInput):
    """
    Class for graphically configuring and generating a
    :class:`~b_asic.signal_generators.Constant` signal generator.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.constant_label = QLabel("Constant")
        self.addWidget(self.constant_label, 0, 0)
        self.constant_input = QLineEdit()
        self.constant_input.setText("1.0")
        self.addWidget(self.constant_input, 0, 1)

    def get_generator(self) -> SignalGenerator:
        constant = self.constant_input.text().strip()
        try:
            if not constant:
                constant = 1.0

            constant = complex(constant)
        except ValueError:
            self._logger.warning(f"Cannot parse constant: {constant} not a number.")
            constant = 0.0

        return Constant(constant)


_GENERATOR_MAPPING = {
    "Constant": ConstantInput,
    "Gaussian": GaussianInput,
    "Impulse": ImpulseInput,
    "Sinusoid": SinusoidInput,
    "Step": StepInput,
    "Uniform": UniformInput,
    "ZeroPad": ZeroPadInput,
    "FromFile": FromFileInput,
}
