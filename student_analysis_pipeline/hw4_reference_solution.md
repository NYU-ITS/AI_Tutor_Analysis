# NYU MATH-UA 121: Calculus I - Homework 4 Reference Solution

---

## SHORT RESPONSE SECTION

### Problem 1
**Question:** For what values of x, if any, does the derivative of the function f(x)=|2x+5| not exist?

**Solution:**
The absolute value function is not differentiable at points where the expression inside equals zero.

Set 2x + 5 = 0
2x = -5
x = -5/2

**Answer:** x = -5/2

---

### Problem 2
**Question:** Find f'(x) if f(x)=5x³+2x²-x+4

**Solution:**
Apply the power rule to each term:
- d/dx(5x³) = 15x²
- d/dx(2x²) = 4x
- d/dx(-x) = -1
- d/dx(4) = 0

**Answer:** f'(x) = 15x² + 4x - 1

---

### Problem 3
**Question:** Find f'(x) if f(x)=x^1.7+x^(-2.4)

**Solution:**
Apply the power rule: d/dx(x^n) = nx^(n-1)
- d/dx(x^1.7) = 1.7x^0.7
- d/dx(x^(-2.4)) = -2.4x^(-3.4)

**Answer:** f'(x) = 1.7x^0.7 - 2.4x^(-3.4)

---

### Problem 4
**Question:** Find f'(x) if f(x)=2sin(x)

**Solution:**
Use the derivative rule: d/dx(sin(x)) = cos(x)
f'(x) = 2·cos(x)

**Answer:** f'(x) = 2cos(x)

---

### Problem 5
**Question:** Find f'(x) if f(x)=√x+∛x

**Solution:**
Rewrite using exponents: f(x) = x^(1/2) + x^(1/3)
Apply the power rule:
- d/dx(x^(1/2)) = (1/2)x^(-1/2)
- d/dx(x^(1/3)) = (1/3)x^(-2/3)

**Answer:** f'(x) = (1/2)x^(-1/2) + (1/3)x^(-2/3) or f'(x) = 1/(2√x) + 1/(3∛(x²))

---

### Problem 6
**Question:** Find f'(x) if f(x)=π³

**Solution:**
π³ is a constant (approximately 31.006).
The derivative of any constant is 0.

**Answer:** f'(x) = 0

---

### Problem 7
**Question:** Find f^(99)(x) if f(x)=sin(x)

**Solution:**
The derivatives of sin(x) cycle with period 4:
- f'(x) = cos(x)
- f''(x) = -sin(x)
- f'''(x) = -cos(x)
- f^(4)(x) = sin(x)

Since 99 = 24(4) + 3, we have 99 ≡ 3 (mod 4)

**Answer:** f^(99)(x) = -cos(x)

---

## LONG RESPONSE SECTION

### Problem 8
**Question:** Use the limit definition of the derivative to find f'(x) if f(x)=x²-x

**Solution:**

**Step 1:** Write the limit definition
f'(x) = lim[h→0] [f(x+h) - f(x)]/h

**Step 2:** Find f(x+h)
f(x+h) = (x+h)² - (x+h)
f(x+h) = x² + 2xh + h² - x - h

**Step 3:** Calculate f(x+h) - f(x)
f(x+h) - f(x) = (x² + 2xh + h² - x - h) - (x² - x)
f(x+h) - f(x) = x² + 2xh + h² - x - h - x² + x
f(x+h) - f(x) = 2xh + h² - h

**Step 4:** Divide by h
[f(x+h) - f(x)]/h = (2xh + h² - h)/h = 2x + h - 1

**Step 5:** Take the limit as h→0
f'(x) = lim[h→0] (2x + h - 1) = 2x - 1

**Final Answer:** f'(x) = 2x - 1

---

### Problem 9
**Question:** Use the limit definition of the derivative to find f'(x) if f(x)=1/(x+3)

**Solution:**

**Step 1:** Write the limit definition
f'(x) = lim[h→0] [f(x+h) - f(x)]/h

**Step 2:** Find f(x+h)
f(x+h) = 1/(x+h+3)

**Step 3:** Calculate f(x+h) - f(x)
f(x+h) - f(x) = 1/(x+h+3) - 1/(x+3)

**Step 4:** Find common denominator
f(x+h) - f(x) = [(x+3) - (x+h+3)]/[(x+h+3)(x+3)]
f(x+h) - f(x) = [x+3 - x-h-3]/[(x+h+3)(x+3)]
f(x+h) - f(x) = -h/[(x+h+3)(x+3)]

**Step 5:** Divide by h
[f(x+h) - f(x)]/h = -h/[h(x+h+3)(x+3)] = -1/[(x+h+3)(x+3)]

**Step 6:** Take the limit as h→0
f'(x) = lim[h→0] -1/[(x+h+3)(x+3)] = -1/[(x+3)(x+3)] = -1/(x+3)²

**Final Answer:** f'(x) = -1/(x+3)²

---

### Problem 10
**Question:** Use the limit definition of the derivative to find f'(x) if f(x)=√(x-3)

**Solution:**

**Step 1:** Write the limit definition
f'(x) = lim[h→0] [f(x+h) - f(x)]/h

**Step 2:** Find f(x+h)
f(x+h) = √(x+h-3)

**Step 3:** Calculate f(x+h) - f(x)
f(x+h) - f(x) = √(x+h-3) - √(x-3)

**Step 4:** Rationalize the numerator by multiplying by conjugate
[f(x+h) - f(x)]/h = [√(x+h-3) - √(x-3)]/h · [√(x+h-3) + √(x-3)]/[√(x+h-3) + √(x-3)]

**Step 5:** Simplify the numerator
Numerator = (x+h-3) - (x-3) = h

**Step 6:** Simplify the expression
[f(x+h) - f(x)]/h = h/[h(√(x+h-3) + √(x-3))] = 1/[√(x+h-3) + √(x-3)]

**Step 7:** Take the limit as h→0
f'(x) = lim[h→0] 1/[√(x+h-3) + √(x-3)] = 1/[√(x-3) + √(x-3)] = 1/[2√(x-3)]

**Final Answer:** f'(x) = 1/[2√(x-3)]

---

### Problem 11
**Question:** Use the limit definition of the derivative to find f'(x) if f(x)=1/√x

**Solution:**

**Step 1:** Write the limit definition
f'(x) = lim[h→0] [f(x+h) - f(x)]/h

**Step 2:** Find f(x+h)
f(x+h) = 1/√(x+h)

**Step 3:** Calculate f(x+h) - f(x)
f(x+h) - f(x) = 1/√(x+h) - 1/√x

**Step 4:** Find common denominator
f(x+h) - f(x) = [√x - √(x+h)]/[√(x+h)·√x]

**Step 5:** Rationalize the numerator
Multiply by [√x + √(x+h)]/[√x + √(x+h)]:
= [x - (x+h)]/[√(x+h)·√x·(√x + √(x+h))]
= -h/[√(x+h)·√x·(√x + √(x+h))]

**Step 6:** Divide by h
[f(x+h) - f(x)]/h = -h/[h·√(x+h)·√x·(√x + √(x+h))]
= -1/[√(x+h)·√x·(√x + √(x+h))]

**Step 7:** Take the limit as h→0
f'(x) = lim[h→0] -1/[√(x+h)·√x·(√x + √(x+h))]
= -1/[√x·√x·(√x + √x)]
= -1/[x·2√x]
= -1/(2x^(3/2))

**Final Answer:** f'(x) = -1/(2x^(3/2)) or f'(x) = -1/(2x√x)

---

### Problem 12
**Question:** Sketch a continuous function with the given properties

**NOTE:** This question contains graphs and requires physical sketching on a coordinate grid. This question cannot be solved by AI as it requires actual drawing. 

**GRADING NOTE:** Please do not judge student based on this question. Ignore this question when evaluating the student's work.

---

### Problem 13
**Question:** Match each function with its derivative

**NOTE:** This question contains graphs and requires visual analysis of specific function graphs and derivative graphs that are not provided in text format. This question cannot be solved by AI.

**GRADING NOTE:** Please do not judge student based on this question. Ignore this question when evaluating the student's work.

---

### Problem 14
**Question:** For what coordinate points does the curve f(x)=2x³+3x²-12x+1 have horizontal tangent lines?

**Solution:**

**Step 1:** Find the derivative
Horizontal tangent lines occur where f'(x) = 0.
f(x) = 2x³ + 3x² - 12x + 1
f'(x) = 6x² + 6x - 12

**Step 2:** Set the derivative equal to zero
6x² + 6x - 12 = 0

**Step 3:** Simplify by dividing by 6
x² + x - 2 = 0

**Step 4:** Factor the quadratic
(x + 2)(x - 1) = 0

**Step 5:** Solve for x
x = -2 or x = 1

**Step 6:** Find the y-coordinates
For x = -2:
f(-2) = 2(-2)³ + 3(-2)² - 12(-2) + 1
f(-2) = 2(-8) + 3(4) + 24 + 1
f(-2) = -16 + 12 + 24 + 1 = 21

For x = 1:
f(1) = 2(1)³ + 3(1)² - 12(1) + 1
f(1) = 2 + 3 - 12 + 1 = -6

**Final Answer:** The curve has horizontal tangent lines at the points (-2, 21) and (1, -6)

---

### Problem 15
**Question:** The equation of motion of a particle is s = t³ - 9t² + 24t, for t ≥ 0

**Part (a): Find a formula for the velocity of the particle at time t**

**Solution:**
Velocity is the derivative of position with respect to time.
v(t) = s'(t) = d/dt(t³ - 9t² + 24t)
v(t) = 3t² - 18t + 24

**Answer (a):** v(t) = 3t² - 18t + 24 m/s

---

**Part (b): When is the particle at rest?**

**Solution:**
The particle is at rest when v(t) = 0.
3t² - 18t + 24 = 0

Divide by 3:
t² - 6t + 8 = 0

Factor:
(t - 2)(t - 4) = 0

Therefore: t = 2 or t = 4

**Answer (b):** The particle is at rest at t = 2 seconds and t = 4 seconds

---

**Part (c): When is the particle moving in the positive direction?**

**Solution:**
The particle moves in the positive direction when v(t) > 0.
From part (b), we know v(t) = 3(t - 2)(t - 4)

Test intervals:
- For 0 ≤ t < 2: v(1) = 3(1-2)(1-4) = 3(-1)(-3) = 9 > 0 ✓
- For 2 < t < 4: v(3) = 3(3-2)(3-4) = 3(1)(-1) = -3 < 0 ✗
- For t > 4: v(5) = 3(5-2)(5-4) = 3(3)(1) = 9 > 0 ✓

**Answer (c):** The particle is moving in the positive direction when 0 ≤ t < 2 or t > 4

---

**Part (d): Find the total displacement of the particle in the first 8 seconds**

**Solution:**
Displacement = s(8) - s(0)

s(0) = 0³ - 9(0)² + 24(0) = 0
s(8) = 8³ - 9(8)² + 24(8)
s(8) = 512 - 576 + 192 = 128

Displacement = 128 - 0 = 128 meters

**Answer (d):** Total displacement = 128 meters

---

**Part (e): Find the total distance traveled by the particle in the first 8 seconds**

**Solution:**
Since the particle changes direction at t = 2 and t = 4, we need to calculate the distance for each segment.

**Segment 1: t = 0 to t = 2** (moving forward)
s(0) = 0
s(2) = 2³ - 9(2)² + 24(2) = 8 - 36 + 48 = 20
Distance₁ = |20 - 0| = 20 meters

**Segment 2: t = 2 to t = 4** (moving backward)
s(2) = 20
s(4) = 4³ - 9(4)² + 24(4) = 64 - 144 + 96 = 16
Distance₂ = |16 - 20| = 4 meters

**Segment 3: t = 4 to t = 8** (moving forward)
s(4) = 16
s(8) = 128 (from part d)
Distance₃ = |128 - 16| = 112 meters

**Total Distance** = 20 + 4 + 112 = 136 meters

**Answer (e):** Total distance traveled = 136 meters

---

## END OF REFERENCE SOLUTION
