import java.util.List;

/**
 * @param positions [x, y, vx, vy] per particle
 */
public record DynamicData(double t, List<double[]> positions) {
}