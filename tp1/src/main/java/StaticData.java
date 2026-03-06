import java.util.List;

public class StaticData {
    public final long           N;
    public final double         L;
    public final List<double[]> radiiAndProps;  // [radius, property] per particle

    public StaticData(long N, double L, List<double[]> radiiAndProps) {
        this.N = N; this.L = L; this.radiiAndProps = radiiAndProps;
    }
}
