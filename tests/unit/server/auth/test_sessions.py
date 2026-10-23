from tiroir.server.auth.sessions import SignInThrottle, SlidingWindow


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


def test_throttle_blocks_a_handle_after_ten_failures() -> None:
    # Given
    throttle = SignInThrottle(Clock())
    for address in range(10):
        throttle.failed("alice", f"10.0.0.{address}")

    # When
    blocked = throttle.blocked("alice", "10.0.0.99")

    # Then
    assert blocked
    assert not throttle.blocked("bob", "10.0.0.99")


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
