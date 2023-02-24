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

    def _parse_number(self, string, _type, name, default):
        string = string.strip()
        try:
            if not string:
                return default
            return _type(string)
        except ValueError:
            self._logger.warning(
                f"Cannot parse {name}: {string} not a {_type.__name__}, setting to"
                f" {default}"
            )
            return default


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
        self.input_sequence.setPlaceholderText("0.1, -0.2, 0.7")
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
        self.frequency_input.setText("0.1")
        self.addWidget(self.frequency_input, 0, 1)

        self.phase_label = QLabel("Phase")
        self.addWidget(self.phase_label, 1, 0)
        self.phase_input = QLineEdit()
        self.phase_input.setText("0.0")
        self.addWidget(self.phase_input, 1, 1)

    def get_generator(self) -> SignalGenerator:
        frequency = self._parse_number(
            self.frequency_input.text(), float, "Frequency", 0.1
        )
        phase = self._parse_number(self.phase_input.text(), float, "Phase", 0.0)
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
        scale = self._parse_number(
            self.scale_input.text(), float, "Standard deviation", 1.0
        )
        loc = self._parse_number(self.loc_input.text(), float, "Average value", 0.0)
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
        low = self._parse_number(self.low_input.text(), float, "Lower bound", -1.0)
        high = self._parse_number(self.high_input.text(), float, "Upper bound", 1.0)
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
        constant = self._parse_number(
            self.constant_input.text(), complex, "Constant", 1.0
        )
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
