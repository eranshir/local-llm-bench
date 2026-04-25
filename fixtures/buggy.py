def sum_up_to(n):
    """Return the sum of integers from 1 to n inclusive."""
    total = 0
    # BUG: loop bound should be range(1, n+1), using range(1, n) misses the last value.
    for i in range(1, n):
        total += i
    return total


if __name__ == "__main__":
    # Expected: sum_up_to(10) == 55
    # Actual (with bug): 45
    print(sum_up_to(10))
