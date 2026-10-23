from tiroir.server.auth.sessions import (
    HANDLE_DELAY_MAX_SECONDS,
    HANDLE_DELAY_STEP_SECONDS,
    SignInThrottle,
    SlidingWindow,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_window_is_full_at_its_limit() -> None:
    # Given
    window = SlidingWindow(3, 60, Clock())
    for _ in range(3):
        window.record("alice")

    # When
    full = window.full("alice")

    # Then
    assert full
    assert not window.full("bob")


def test_window_forgets_events_older_than_its_length() -> None:
    # Given
    clock = Clock()
    window = SlidingWindow(3, 60, clock)
    for _ in range(3):
        window.record("alice")
    clock.now += 60

    # When
    full = window.full("alice")

    # Then
    assert not full


def test_throttle_blocks_an_address_after_ten_failures_on_a_handle() -> None:
    # Given
    throttle = SignInThrottle(Clock())
    for _ in range(10):
        throttle.failed("alice", "10.0.0.1")

    # When
    blocked = throttle.blocked("alice", "10.0.0.1")

    # Then
    assert blocked
    assert not throttle.blocked("alice", "10.0.0.2")
    assert not throttle.blocked("bob", "10.0.0.1")


def test_failures_from_many_addresses_delay_a_handle_without_blocking_it() -> None:
    # Given
    throttle = SignInThrottle(Clock())
    for address in range(12):
        throttle.failed("alice", f"10.0.0.{address}")

    # When
    delay = throttle.delay("alice")

    # Then
    assert delay == 3 * HANDLE_DELAY_STEP_SECONDS
    assert not throttle.blocked("alice", "10.0.0.99")
    assert throttle.delay("bob") == 0


def test_handle_delay_starts_at_ten_failures_and_is_capped() -> None:
    # Given
    nine, many = SignInThrottle(Clock()), SignInThrottle(Clock())
    for address in range(9):
        nine.failed("alice", f"10.0.0.{address}")
    for address in range(1000):
        many.failed("alice", f"10.0.{address // 256}.{address % 256}")

    # When
    delays = (nine.delay("alice"), many.delay("alice"))

    # Then
    assert delays == (0, HANDLE_DELAY_MAX_SECONDS)


def test_throttle_blocks_an_address_trying_many_handles() -> None:
    # Given
    throttle = SignInThrottle(Clock())
    for handle in range(30):
        throttle.failed(f"member{handle}", "10.0.0.1")

    # When
    blocked = throttle.blocked("someone", "10.0.0.1")

    # Then
    assert blocked
    assert not throttle.blocked("someone", "10.0.0.2")
