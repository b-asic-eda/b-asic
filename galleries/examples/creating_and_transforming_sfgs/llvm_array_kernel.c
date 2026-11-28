/* A two-point FFT butterfly: this buffer is input/output, not persistent state. */
void butterfly(float data[2]) {
    float a = data[0];
    float b = data[1];
    data[0] = a + b;
    data[1] = a - b;
}

/* A separate stateful algorithm: one accumulated value persists between calls. */
float accumulate(float x, float *state) {
    *state = *state + x;
    return *state;
}
