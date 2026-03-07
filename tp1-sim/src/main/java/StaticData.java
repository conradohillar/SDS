import java.util.List;

/**
 * @param radiiAndProps [radius, property] per particle
 */
public record StaticData(long N, double L, List<double[]> radiiAndProps) {
}
