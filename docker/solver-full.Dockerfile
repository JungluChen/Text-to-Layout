FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PATH=/opt/openEMS/bin:/root/.local/bin:${PATH} \
    LD_LIBRARY_PATH=/opt/openEMS/lib:/opt/openEMS/lib64

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git python3 python3-pip python3-venv \
    octave octave-control octave-signal octave-io octave-dev \
    gmsh python3-meshio klayout \
    libhdf5-dev libvtk9-dev libvtk9-qt-dev libboost-all-dev libcgal-dev \
    libtinyxml-dev qtbase5-dev libfftw3-dev libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --recursive https://github.com/thliebig/openEMS-Project.git /tmp/openEMS-Project \
    && cd /tmp/openEMS-Project \
    && ./update_openEMS.sh /opt/openEMS \
    && rm -rf /tmp/openEMS-Project

WORKDIR /work
COPY . /work
RUN python3 -m pip install -e ".[rf,mesh]"

RUN printf "%s\n" \
    "addpath('/opt/openEMS/share/openEMS/matlab');" \
    "addpath('/opt/openEMS/share/CSXCAD/matlab');" \
    > /root/.octaverc

CMD ["textlayout", "doctor"]
