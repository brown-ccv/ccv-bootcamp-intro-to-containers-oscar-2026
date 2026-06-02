# Reproducible Research with Containers on OSCAR

## CCV BootCamp 2026 · Ashok Ragavendran

Center for Computation and Visualization · Brown University

---

## Where to get help

- **Office hours** — drop in any time
- **Docs** — docs.ccv.brown.edu
- **Slack** — `ccv-share` workspace
- **Email** — support@ccv.brown.edu
- **Web** — ccv.brown.edu

---

## Why containers?

A simple, lightweight way to make **both your code and its environment portable**.

Build once → run the same everywhere: your laptop, OSCAR, the cloud.

---

## Use cases

- **BYOE** — bring your own flexible environment to a rigid shared system
- **Reproducible science** — ship code, libraries, data, and scripts as one unit
- **Commercial / certified software** — pin the exact OS a vendor requires
- **Static "fund-once" software** — freeze an unmaintained stack so it still runs
- **Legacy code** — run a 15-year-old distro on today's hardware
- **Host-specific stacks** — weather/atmospheric models, complex toolchains
- **Complex workflows** — distribute and verify an entire pipeline

*Source: apptainer.org*

---

## So what exactly is a container?

A container packages your **application and its dependencies** on top of the host's OS kernel — lighter and faster than a virtual machine.

- VMs + hypervisors abstract **hardware** → run whole operating systems
- Containers + engines abstract the **OS** → run applications

![Containers vs. virtual machines](4da8eb36-de61-4f81-a484-a42146f46dbd.png)

---

## VM vs. container

- A VM carries an **entire guest OS** — gigabytes, slow boot
- A container ships **only the app + dependencies** on the host kernel
- Result: starts in **seconds**, small enough to share, near-native speed

That lightness is exactly why containers fit reproducible research on shared HPC systems like OSCAR.

---

## Container platforms

- **Docker** — the most common engine; great on your laptop, but needs a root daemon → not for shared HPC
- **Apptainer** (formerly Singularity) — built for HPC; runs as *you*, no root daemon → what we use on OSCAR

Both follow the **Open Container Initiative (OCI)** standard, so a Docker image can be converted to and run with Apptainer. That is the whole laptop → cluster trick.

---

## Runtime vs. engine

- A **container runtime** pulls images and runs containers, managing their life cycle
- A **container engine** does more: building, image distribution, orchestration, runtime management

Docker Engine *includes* a runtime but is much more than one — a common point of confusion.

*Source: wiz.io*

---

## Images vs. containers

An **image** is the blueprint; a **container** is the running instance built from it.

- Images are **immutable**
- A running container *can* be modified — but changes are **lost when it stops**

Map of a house (image) vs. the built house (container).

---

## Registries & recipes

- **Registry** — a server that stores and shares images (Docker Hub, Quay, GHCR, NVIDIA NGC). You `pull` and `push`.
- **Recipe** — a text file that builds an image step by step:
  - **Dockerfile** for Docker
  - **Definition file** (`.def`) for Apptainer

Keep the recipe in **GitHub** → anyone can rebuild the same environment.

---

## Mount points (binds)

Locations on the host mounted *into* the running container — like plugging a USB stick into your laptop.

- **Docker** — you must explicitly mount each path (`-v` / `--mount`)
- **Apptainer** — auto-mounts your home directory and runs *as you*, so files you create are owned by you on the host

---

## Ports

Containers can run as a **service** — a web server, database, Jupyter, RStudio.

- You interact over the **network**, not the shell
- Map host ↔ container ports so traffic reaches the app
- Run many containers from one image on different ports

---

## How do we leverage this?

![Porting an environment across platforms](3c9388a2-14b4-44b1-9357-1f92a457241f.png)

Prototype in Docker on your laptop → need more power → move to OSCAR (or the cloud). On the cluster you convert the Docker container into an **Apptainer image**.

---

## Two ways to port a container

- **Push to a registry, pull on OSCAR**
  `apptainer build my.sif docker://user/image:tag`
- **Build locally, copy the file over**
  `docker save` → `scp`/`rsync`/Globus → `apptainer build`

Registry route for public images; file copy when it must stay private.

---

## The commands you'll actually use

| Task | Docker | Apptainer |
|---|---|---|
| Download an image | `docker pull` | `apptainer pull` |
| Build from a recipe | `docker build` | `apptainer build` |
| Run default command | `docker run` | `apptainer run` |
| Run a specific command | `docker exec` | `apptainer exec` |
| Interactive shell | `docker run -it … bash` | `apptainer shell` |

Docker has a **daemon** (`docker ps`). Apptainer has **none** — an image is just a `.sif` file you run as a normal process.

---

## Demo: lolcow with Docker

A tiny image whose only job is to print an ASCII cow — easy to see when it works.

```bash
# Pull and run the default command
docker pull godlovedc/lolcow
docker run godlovedc/lolcow

# Or run a specific command inside it
docker run -dit --name lolcow godlovedc/lolcow
docker ps
docker exec -it lolcow cowsay moo
```

---

## Demo: lolcow with Apptainer

```bash
# Pull and convert to a .sif file
apptainer pull docker://sylabsio/lolcow

# Run the default command
apptainer run lolcow_latest.sif

# Exec a specific command
apptainer exec lolcow_latest.sif cowsay moo

# Drop into an interactive shell
apptainer shell lolcow_latest.sif
```

---

## Build your own: Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ./src /opt/src
WORKDIR /opt/src
CMD ["python", "main.py"]
```

```bash
docker build -t myanalysis:1.0 .
```

---

## Build your own: Apptainer .def

```text
Bootstrap: docker
From: python:3.12-slim

%files
    requirements.txt /tmp/requirements.txt
    src /opt/src

%post
    apt-get update && apt-get install -y --no-install-recommends git
    pip install --no-cache-dir -r /tmp/requirements.txt

%runscript
    cd /opt/src && exec python main.py
```

```bash
apptainer build myanalysis.sif myanalysis.def
```

> Building a `.def` may need `--fakeroot`. Often easiest to build with Docker and convert.

---

## Convert Docker → Apptainer

On an OSCAR **login node** (compute nodes have no internet):

```bash
# Straight from a registry
apptainer build myanalysis.sif docker://user/myanalysis:1.0
```

```bash
# Or from a saved local image
docker save myanalysis:1.0 -o myanalysis.tar      # laptop
scp myanalysis.tar you@ssh.ccv.brown.edu:/oscar/scratch/$USER/
apptainer build myanalysis.sif docker-archive://myanalysis.tar
```

---

## On OSCAR: setup & binds

Apptainer is **pre-installed** on compute nodes — no `module load` needed.

```bash
# Send the image cache to scratch (home is only ~100 GB)
mkdir -p ~/scratch/.apptainer
export APPTAINER_CACHEDIR=~/scratch/.apptainer
```

```bash
# Bind extra OSCAR paths into the container
apptainer shell --bind /oscar/data/cbc,/oscar/scratch/$USER:/scratch lolcow_latest.sif
export APPTAINER_BINDPATH="/oscar/home/$USER,/oscar/scratch/$USER,/oscar/data"
```

---

## On OSCAR: GPUs & Slurm

```bash
# --nv exposes the host NVIDIA driver/GPUs
apptainer exec --nv mycontainer.sif nvidia-smi
```

```bash
#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00

export APPTAINER_BINDPATH="/oscar/home/$USER,/oscar/scratch/$USER,/oscar/data"
apptainer exec --nv /oscar/data/yourlab/mycontainer.sif python train.py
```

> Pull/build on a login node first — compute nodes have **no internet**. Images are read-only; use `--user` or rebuild to add packages.

---

## Tips & tricks

- `apptainer … --cleanenv` — start with a clean environment
- `apptainer … --compat` — Docker-like, more isolated mode
- `apptainer build --fakeroot …` — build without real root
- `docker system prune` — reclaim disk space
- `docker image rm <image>` — delete a local image


---

## Thank you!

Questions? Find us at **office hours**, on **`ccv-share`** Slack, or **support@ccv.brown.edu**

- Apptainer guide — apptainer.org/docs/user/latest
- OSCAR containers — docs.ccv.brown.edu
- OCI — opencontainers.org
