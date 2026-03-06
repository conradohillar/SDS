import java.util.List;

public class DynamicData {
    public final double         t;
    public final List<double[]> positions;  // [x, y, vx, vy] per particle

    public DynamicData(double t, List<double[]> positions) {
        this.t = t; this.positions = positions;
    }
}