# NYU MATH-UA 121: Calculus I - Homework 9 Reference Solution

---

## SHORT RESPONSE SECTION

### Problem 1
**Question:** Evaluate lim(x→∞) (e^(2x) - e^x) / (3e^(2x) + e^x)

**Solution:**
Divide every term by the highest power in the denominator, which is e^(2x).
lim(x→∞) [ (e^(2x)/e^(2x) - e^x/e^(2x)) / (3e^(2x)/e^(2x) + e^x/e^(2x)) ]
= lim(x→∞) [ (1 - e^(-x)) / (3 + e^(-x)) ]

As x→∞, e^(-x) approaches 0.
= (1 - 0) / (3 + 0) = 1/3

**Answer:** 1/3

---

### Problem 2
**Question:** Evaluate lim(x→1) (x^5 - 1) / (x^8 - 1)

**Solution:**
Substitute x=1 to check the form: (1^5 - 1)/(1^8 - 1) = 0/0 (Indeterminate).
Use L'Hôpital's Rule:
lim(x→1) [ d/dx(x^5 - 1) / d/dx(x^8 - 1) ] = lim(x→1) [ 5x^4 / 8x^7 ]
= 5(1)^4 / 8(1)^7 
= 5/8

**Answer:** 5/8

---

### Problem 3
**Question:** Find all critical numbers for the function f(x)=|x-8| or state that there are none.

**Solution:**
A critical number occurs where f'(x) = 0 or f'(x) is undefined.
The function f(x)=|x-8| has a "corner" (sharp turn) at x=8, so the derivative is undefined at x=8.
For x ≠ 8, the slope is either 1 or -1, so it is never 0.

**Answer:** x = 8

---

### Problem 4
**Question:** Find all critical numbers for the function f(x)=xe^x or state that there are none.

**Solution:**
Find the derivative using the product rule:
f'(x) = (1)e^x + x(e^x) = e^x(1 + x)

Set f'(x) = 0:
e^x(1 + x) = 0
Since e^x ≠ 0 for all real x, we must have 1 + x = 0, so x = -1.
The derivative is defined everywhere.

**Answer:** x = -1

---

### Problem 5
**Question:** Find all critical numbers for the function f(x)=ln(x) or state that there are none.

**Solution:**
Find the derivative:
f'(x) = 1/x

Set f'(x) = 0:
1/x = 0 has no solution.
The derivative is undefined at x=0, but x=0 is not in the domain of ln(x) (domain is x > 0). Therefore, there are no critical numbers in the domain.

**Answer:** There are none

---

### Problem 6
**Question:** Find all critical numbers for the function f(x)=arctan(x^5) or state that there are none.

**Solution:**
Find the derivative using the chain rule:
f'(x) = [ 1 / (1 + (x^5)^2) ] · 5x^4 
f'(x) = 5x^4 / (1 + x^10)

Set f'(x) = 0:
5x^4 = 0 implies x = 0.
The denominator 1 + x^10 is never zero, so the derivative exists everywhere.

**Answer:** x = 0

---

### Problem 7
**Question:** Find all critical numbers for the function f(x)=x^2 / (x+1) or state that there are none.

**Solution:**
Find the derivative using the quotient rule:
f'(x) = [ 2x(x+1) - x^2(1) ] / (x+1)^2
f'(x) = (2x^2 + 2x - x^2) / (x+1)^2
f'(x) = (x^2 + 2x) / (x+1)^2
f'(x) = x(x+2) / (x+1)^2

Set f'(x) = 0:
x(x+2) = 0 implies x = 0 or x = -2.
The derivative is undefined at x = -1, but x = -1 is not in the domain of the function.

**Answer:** x = 0, x = -2

---

### Problem 8
**Question:** True or false: f(x)=1/(x-4) is guaranteed by the Extreme Value Theorem to attain a maximum value on the interval [-2, 2].

**Solution:**
The Extreme Value Theorem requires the function to be continuous on the closed interval.
The function f(x)=1/(x-4) has a discontinuity at x=4.
Since x=4 is **not** in the interval [-2, 2], the function is continuous on the entire interval [-2, 2]. Therefore, EVT applies.

**Answer:** True

---

### Problem 9
**Question:** True or false: If f(x) is continuous everywhere and f(c) is a local maximum, then f'(c)=0

**Solution:**
This is false. A local maximum can occur at a point where the derivative is undefined (e.g., a sharp corner or cusp, like f(x)=-|x| at x=0). At a local max, f'(c) is either 0 OR undefined.

**Answer:** False

---

## LONG RESPONSE SECTION

### Problem 10
**Question:** Evaluate the limit lim(x→0) (x·cos(x) - sin(x)) / (sin(x) - x)

**Solution:**

**Step 1:** Check form
At x=0, (0·1 - 0) / (0 - 0) = 0/0. Apply L'Hôpital's Rule.

**Step 2:** Apply L'Hôpital (1st time)
lim(x→0) [ (cos(x) - x·sin(x) - cos(x)) / (cos(x) - 1) ]
= lim(x→0) [ -x·sin(x) / (cos(x) - 1) ]
At x=0, this is 0/(1-1) = 0/0. Apply L'Hôpital's Rule again.

**Step 3:** Apply L'Hôpital (2nd time)
lim(x→0) [ -(1·sin(x) + x·cos(x)) / -sin(x) ]
= lim(x→0) [ (sin(x) + x·cos(x)) / sin(x) ]
At x=0, this is 0/0. Apply L'Hôpital's Rule again.

**Step 4:** Apply L'Hôpital (3rd time)
lim(x→0) [ (cos(x) + (1·cos(x) - x·sin(x))) / cos(x) ]
= lim(x→0) [ (2cos(x) - x·sin(x)) / cos(x) ]

**Step 5:** Evaluate
= (2cos(0) - 0) / cos(0) 
= (2(1) - 0) / 1 
= 2

**Answer:** 2

---

### Problem 11
**Question:** Evaluate the limit lim(t→0+) csc(t)^(arccos(t)/ln(t))

**Solution:**

**Step 1:** Use logarithms
Let y = csc(t)^(arccos(t)/ln(t)). 
Then ln(y) = (arccos(t)/ln(t)) · ln(csc(t)).
We want to find lim(t→0+) ln(y) = lim(t→0+) [ arccos(t) · ln(csc(t)) / ln(t) ].

**Step 2:** Separate terms
lim(t→0+) arccos(t) = arccos(0) = π/2.
Now evaluate the remaining limit: L = lim(t→0+) [ ln(csc(t)) / ln(t) ].
Form: ln(∞)/(-∞) = ∞/∞. Apply L'Hôpital.

**Step 3:** Apply L'Hôpital
L = lim(t→0+) [ (1/csc(t)) · (-csc(t)cot(t)) ] / [ 1/t ]
L = lim(t→0+) [ -cot(t) / (1/t) ]
L = lim(t→0+) [ -t / tan(t) ]
Using standard limit lim(t→0) tan(t)/t = 1, we get L = -1.

**Step 4:** Combine
lim(t→0+) ln(y) = (π/2) · (-1) = -π/2.
Therefore, y = e^(-π/2).

**Answer:** e^(-π/2)

---

### Problem 12
**Question:** Evaluate the limit lim(x→1) tan(πx/2) · ln(x)

**Solution:**

**Step 1:** Check form
tan(π/2) · ln(1) = ∞ · 0. Indeterminate product.
Rewrite as quotient: lim(x→1) [ ln(x) / cot(πx/2) ].

**Step 2:** Check quotient form
ln(1) / cot(π/2) = 0/0. Apply L'Hôpital.

**Step 3:** Apply L'Hôpital
lim(x→1) [ (1/x) / (-csc²(πx/2) · π/2) ]

**Step 4:** Evaluate
= (1/1) / (-(1)² · π/2) 
= 1 / (-π/2) 
= -2/π

**Answer:** -2/π

---

### Problem 13
**Question:** Evaluate the limit lim(x→0+) (1/x - 1/(e^x - 1))

**Solution:**

**Step 1:** Combine fractions
Form is ∞ - ∞.
lim(x→0+) [ ((e^x - 1) - x) / (x(e^x - 1)) ]

**Step 2:** Check form and Apply L'Hôpital
Form is 0/0.
lim(x→0+) [ (e^x - 1) / ( (1)(e^x - 1) + x(e^x) ) ]
At x=0, this is 0/0. Apply L'Hôpital again.

**Step 3:** Apply L'Hôpital (2nd time)
lim(x→0+) [ e^x / ( e^x + (1·e^x + x·e^x) ) ]
= lim(x→0+) [ e^x / (2e^x + xe^x) ]

**Step 4:** Evaluate
= e^0 / (2e^0 + 0) 
= 1 / (2(1)) 
= 1/2

**Answer:** 1/2

---

### Problem 14
**Question:** Evaluate the limit lim(x→∞) (e^x + x)^(1/x)

**Solution:**

**Step 1:** Use logarithms
Let y = (e^x + x)^(1/x). 
Then ln(y) = ln(e^x + x) / x.

**Step 2:** Evaluate limit of ln(y)
lim(x→∞) ln(e^x + x) / x is form ∞/∞. Apply L'Hôpital.
lim(x→∞) [ ( (e^x + 1)/(e^x + x) ) / 1 ] 
= lim(x→∞) [ (e^x + 1) / (e^x + x) ]

**Step 3:** Apply L'Hôpital again
Form ∞/∞.
lim(x→∞) [ e^x / (e^x + 1) ]
Apply L'Hôpital again:
lim(x→∞) [ e^x / e^x ] = 1

**Step 4:** Final Answer
ln(y) → 1, so y → e^1 = e.

**Answer:** e

---

### Problem 15
**Question:** Sketch the graph of a function f(x) with specific properties.

**NOTE:** This question requires physically sketching a graph on a specific coordinate grid provided in the source file. An AI cannot perform the physical drawing required.

**GRADING NOTE:** Please do not judge student based on this question. Ignore this question when evaluating the student's work.

---

### Problem 16
**Question:** Sketch the graph of a function f(x) with specific properties.

**NOTE:** This question requires physically sketching a graph on a specific coordinate grid provided in the source file. An AI cannot perform the physical drawing required.

**GRADING NOTE:** Please do not judge student based on this question. Ignore this question when evaluating the student's work.

---

### Problem 17
**Question:** If f(x) = x^2 e^x, -5 ≤ x ≤ 5, find the absolute minimum value and the absolute maximum value of the function on the stated interval.

**Solution:**

**Step 1:** Find critical points
f'(x) = 2xe^x + x^2 e^x = xe^x (2 + x).
Set f'(x)=0: x=0 and x=-2. Both are in the interval.

**Step 2:** Evaluate at critical points
f(0) = 0^2 e^0 = 0.
f(-2) = (-2)^2 e^(-2) = 4/e^2 ≈ 0.54.

**Step 3:** Evaluate at endpoints
f(-5) = (-5)^2 e^(-5) = 25/e^5 ≈ 0.17.
f(5) = 5^2 e^5 = 25e^5 ≈ 3710.

**Step 4:** Compare values
Minimum is 0. Maximum is 25e^5.

**Answer:** Absolute Min: 0, Absolute Max: 25e^5

---

### Problem 18
**Question:** If f(x) = 2x + 1/x^2, -2 ≤ x ≤ 10, find the absolute minimum value and the absolute maximum value of the function on the stated interval.

**Solution:**

**Step 1:** Analyze continuity
The function is undefined at x=0. Since 0 is in the interval [-2, 10], the function is not continuous on the closed interval.
As x → 0 (from either side), 1/x^2 → ∞, so f(x) → ∞. Thus, there is **no absolute maximum**.

**Step 2:** Find critical points for minimum
f'(x) = 2 - 2x^(-3) = 2 - 2/x^3.
Set f'(x)=0 implies 2 = 2/x^3 implies x^3 = 1 implies x = 1.

**Step 3:** Check values
On the interval [-2, 0): Endpoint x = -2.
f(-2) = 2(-2) + 1/4 = -4 + 0.25 = -3.75.
On the interval (0, 10]: Critical point x = 1, Endpoint x = 10.
f(1) = 2(1) + 1 = 3.
f(10) = 20 + 0.01 = 20.01.
Comparing local minimums/endpoints: -3.75 (at x = -2) is lower than 3 (at x = 1).

**Answer:** Absolute Min: -3.75, Absolute Max: None (DNE)

---

### Problem 19
**Question:** If g(x) = √(4 - x^2) on [-2, 1], find the absolute minimum value and the absolute maximum value of the function on the stated interval.

**Solution:**

**Step 1:** Find critical points
g'(x) = (1 / 2√(4-x^2)) · (-2x) = -x / √(4-x^2).
Set g'(x)=0 implies x = 0. (In interval).

**Step 2:** Evaluate at critical points
g(0) = √(4-0) = 2.

**Step 3:** Evaluate at endpoints
g(-2) = √(4-4) = 0.
g(1) = √(4-1) = √3 ≈ 1.732.

**Step 4:** Compare values
Minimum is 0. Maximum is 2.

**Answer:** Absolute Min: 0, Absolute Max: 2

---

## END OF REFERENCE SOLUTION