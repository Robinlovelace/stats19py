import sys, time, resource, stats19
case = sys.argv[1]
t = time.time()
if case == "cas2019":
    df = stats19.get_casualties(2019, silent=True)
elif case == "veh2019":
    df = stats19.get_vehicles(2019, silent=True)
elif case == "col5":
    df = stats19.get_collisions(5, silent=True)
n = None if df is None else len(df)
print(f"{case}: rows={n} secs={time.time()-t:.1f} maxrss_MB={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss//1024}")
