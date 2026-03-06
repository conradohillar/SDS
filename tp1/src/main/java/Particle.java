import static java.lang.Math.pow;
import static java.lang.Math.sqrt;

public record Particle(double x, double y, double radius) {
    public double distanceTo(Particle p) {
        double distanceX =  x - p.x - radius - p.radius;
        double distanceY = y - p.y - radius - p.radius;
        return sqrt(pow(distanceX, 2) + pow(distanceY, 2));
    }
}
