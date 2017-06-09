# regress
For batch regression testing - running code to produce output and then comparing the produced .fits files 

WIP

## Usage
```
usage: regress.py [-h] [-r <root data path>] [-o <output path>]
                  [-e <path containing executable>]
                  [-D <dir to diff> <dir to diff>] [-d <dir to diff>] [--cte]
                  [--clean CLEAN] [--move <path> <path>] [-n MAXTHREADS]
                  [--find [OPTFIND [OPTFIND ...]]]

Regression test suite

optional arguments:
  -h, --help            show this help message and exit
  -r <root data path>   Root path to regression test data
  -o <output path>, --outPath <output path>
                        Root path to dump all output
  -e <path containing executable>, --execPath <path containing executable>
                        Root path to executables
  -D <dir to diff> <dir to diff>, --diffOnly <dir to diff> <dir to diff>
                        Do not run tests, only compare output in first dir to
                        that in second
  -d <dir to diff>, --diffOnTheFly <dir to diff>
                        Diff each current test output in <out path> to those
                        in <path to output to diff>. Do this after each test
                        is complete
  --cte                 Only complete tests and comparisons for files with
                        PCTECORR = PERFORM
  --clean CLEAN         Clean <root data path> leaving only *raw.fits files.
  --move <path> <path>  Move all none *raw.fits files in <1st path> to <2nd
                        path>/results
  -n MAXTHREADS, --maxThreads MAXTHREADS
                        The maximum number of threads to use to spawn jobs
  --find [OPTFIND [OPTFIND ...]]
                        Recurse through 1st arg <path> for files with 2nd arg
                        <keyword> set to 3rd arg <value> and print all found
```

Won't be bullet proof.
