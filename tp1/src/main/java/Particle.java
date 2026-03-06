public record Particle(long id, double x, double y, double radius) {
    public boolean overlaps(Particle p) {
        double dx = p.x() - x();
        double dy = p.y() - y();
        double distanceSquared = dx * dx + dy * dy;
        double minDistance = p.radius() + radius();

        return (distanceSquared < minDistance * minDistance);
    }
}
