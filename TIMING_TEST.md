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

## Before launch: five people (rules written before anyone is timed)

- Five real viewers, each doing both methods in the random order the script picks.
- Reported as what five people did: each person's two times, the median of each method, and median
  happiness. Five people is not a statistical test, so no p-value and no general claim.
- The front page may show a speed line only if both hold: iCinema's median time is lower than
  browsing's, and iCinema's median happiness is at least browsing's. Otherwise nothing is claimed and
  the result is still reported in the README.
- The paired Wilcoxon test stays for 10+ people, after launch.
