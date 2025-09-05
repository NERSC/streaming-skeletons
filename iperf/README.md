# iperf performance tests

## Install

```sh
uv sync
```

## Edit configuration

See [piperf3](https://github.com/swelborn/piperf3) for configuration information. Set up a `.env` file for a particular run type.

## Submit a script to slurm

```sh
cd scripts/perlmutter/cpu-cpu
sbatch piperf.sh
```