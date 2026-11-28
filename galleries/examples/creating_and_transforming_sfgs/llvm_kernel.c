/* A fixed loop and compile-time branches become straight-line arithmetic. */
float kernel(float x, float gain) {
    float result = x;
    for (int i = 0; i < 4; ++i) {
        if (i % 2 == 0)
            result = result * gain;
        else
            result = result + x;
    }
    return result;
}
