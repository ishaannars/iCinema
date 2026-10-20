# Decision-time test

The question: how long until someone has picked a movie they'd actually press play on?

1. Each person sets up iCinema first (Steps 1–3, any likes they want). This is not timed.
2. Run `python timing_test.py`. It picks a random order for the two methods, so neither always goes first.
3. **iCinema:** open the app and stop when you'd press play on something.
4. **Browse:** open your usual streaming app's home screen and stop when you'd press play.
5. After each one, rate how happy you are with the pick from 1 to 5.

Rules: same device, same time of day if possible, no talking during a run. People should be real
viewers, not people who helped build the app. The README updates itself after every person, and a
paired Wilcoxon test is added once 10 people have done both.
