from era.models.entities import Question

# Entirely synthetic demonstration items. They are not validated exam questions.
SAMPLE_QUESTIONS = [
    Question("SYN-PHY-001", "Physics", "Mechanics", "A body travels 10 m in 2 s. What is its average speed?", ("2 m/s", "5 m/s", "10 m/s", "20 m/s"), 1, -1.2),
    Question("SYN-PHY-002", "Physics", "Mechanics", "Which quantity is a vector?", ("Mass", "Time", "Velocity", "Temperature"), 2, -0.8),
    Question("SYN-PHY-003", "Physics", "Mechanics", "A 2 kg object accelerates at 3 m/s². What net force acts on it?", ("1.5 N", "5 N", "6 N", "9 N"), 2, -0.3),
    Question("SYN-PHY-004", "Physics", "Mechanics", "If speed doubles while mass is constant, kinetic energy becomes what multiple?", ("2", "3", "4", "8"), 2, 0.1),
    Question("SYN-PHY-005", "Physics", "Mechanics", "A projectile is launched horizontally from a height. Ignoring drag, which component remains constant?", ("Vertical velocity", "Horizontal velocity", "Total velocity", "Vertical displacement"), 1, 0.4),
    Question("SYN-PHY-006", "Physics", "Mechanics", "For a conservative force, work around a closed path is:", ("Always positive", "Always negative", "Zero", "Equal to path length"), 2, 0.7),
    Question("SYN-MATH-001", "Mathematics", "Algebra", "Solve 2x + 4 = 10.", ("2", "3", "4", "7"), 1, -1.0),
    Question("SYN-MATH-002", "Mathematics", "Algebra", "If x² = 49 and x is positive, x equals:", ("-7", "0", "7", "49"), 2, -0.5),
    Question("SYN-MATH-003", "Mathematics", "Algebra", "Factor x² - 9.", ("(x-9)(x+1)", "(x-3)(x+3)", "(x-3)²", "(x+9)(x-1)"), 1, 0.0),
    Question("SYN-MATH-004", "Mathematics", "Algebra", "If f(x)=x², what is f'(3)?", ("3", "6", "9", "12"), 1, 0.3),
    Question("SYN-MATH-005", "Mathematics", "Algebra", "For positive x, if log₂(x)=5, then x is:", ("10", "16", "25", "32"), 3, 0.6),
    Question("SYN-MATH-006", "Mathematics", "Algebra", "The roots of x² - 4x + 4 = 0 are:", ("Distinct real roots", "A repeated real root", "No real roots", "Two imaginary roots"), 1, 0.8),
    Question("SYN-PHY-007", "Physics", "Mechanics", "A spring obeys Hooke's law. If extension triples, the elastic potential energy becomes:", ("3 times", "6 times", "9 times", "27 times"), 2, 1.1),
    Question("SYN-MATH-007", "Mathematics", "Algebra", "For a differentiable function, a local minimum may occur where:", ("Derivative is necessarily positive", "Derivative is zero", "Function is undefined", "Second derivative must be negative"), 1, 1.2),
    Question("SYN-PHY-008", "Physics", "Mechanics", "Two equal masses move with equal speeds in opposite directions. Their total momentum is:", ("Zero", "Positive", "Negative", "Equal to kinetic energy"), 0, -0.1),
    Question("SYN-MATH-008", "Mathematics", "Algebra", "If a matrix has determinant zero, it is:", ("Always orthogonal", "Singular", "Always diagonal", "Always identity"), 1, 0.9),
]
