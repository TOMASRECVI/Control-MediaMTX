# Compila un ffmpeg ESTATICO para ARMv7 (Cortex-A9, confirmado via
# .ARM.attributes del binario "box" del BM3000) con soporte SRT.
#
# Al ser 100% estatico (musl libc), NO depende de la uClibc del propio
# BM3000 ni de su toolchain propietario de HiSilicon -- solo necesita
# que el kernel Linux del dispositivo entienda las syscalls basicas
# (socket/read/write/mmap...), disponibles desde kernels muy antiguos.
#
# Uso (en un servidor con Docker, p.ej. 192.168.1.147):
#   docker build -t bm3000-ffmpeg-builder .
#   docker create --name extract bm3000-ffmpeg-builder
#   docker cp extract:/out/ffmpeg_armv7 .
#   docker rm extract
#
# El resultado es un unico fichero "ffmpeg_armv7" que se copia al
# encoder por telnet/ftp (ver README.md).

FROM dockcross/linux-armv7 AS build

WORKDIR /src

# --- libsrt (Haivision) ---
RUN git clone --depth 1 --branch v1.5.3 https://github.com/Haivision/srt.git srt && \
    cd srt && \
    mkdir build && cd build && \
    cmake .. \
        -DCMAKE_TOOLCHAIN_FILE= \
        -DCMAKE_C_COMPILER=$CC \
        -DCMAKE_CXX_COMPILER=$CXX \
        -DCMAKE_INSTALL_PREFIX=/opt/armv7 \
        -DENABLE_SHARED=OFF \
        -DENABLE_STATIC=ON \
        -DENABLE_APPS=OFF \
        -DENABLE_ENCRYPTION=OFF \
        -DCMAKE_C_FLAGS="-static-libgcc" \
        -DCMAKE_CXX_FLAGS="-static-libgcc -static-libstdc++" \
    && make -j"$(nproc)" && make install

# Sin -DUSE_ENCLIB, con ENABLE_ENCRYPTION=OFF, srt.pc no declara ninguna
# dependencia de OpenSSL -- si se pusieran ambas a la vez, srt.pc queda con
# "Requires.private: openssl" y pkg-config falla al resolverla (no hay
# openssl cross-compilado aqui), y ffmpeg lo reporta como "srt not found"
# sin mas detalle. Verificamos aqui para no repetir ese diagnostico a ciegas.
ENV PKG_CONFIG_PATH=/opt/armv7/lib/pkgconfig
RUN echo "--- pkg-config --exists (sin --static) ---"; \
    pkg-config --exists --print-errors "srt >= 1.3.0" && echo OK || echo FALLO; \
    echo "--- pkg-config --exists --static (esto es lo que usa ffmpeg configure) ---"; \
    pkg-config --exists --print-errors --static "srt >= 1.3.0" && echo OK || echo FALLO; \
    echo "--- srt.pc ---"; cat /opt/armv7/lib/pkgconfig/srt.pc; \
    echo "--- haisrt.pc ---"; cat /opt/armv7/lib/pkgconfig/haisrt.pc || true

# --- ffmpeg (solo lo imprescindible: demux RTSP, mux MPEG-TS, remux, protocolo SRT) ---
RUN git clone --depth 1 --branch n6.1 https://github.com/FFmpeg/FFmpeg.git ffmpeg && \
    cd ffmpeg && \
    (./configure \
        --arch=arm --target-os=linux --cross-prefix=$CROSS_TRIPLE- \
        --enable-cross-compile \
        --pkg-config=pkg-config \
        --extra-cflags="-I/opt/armv7/include" \
        --extra-ldflags="-L/opt/armv7/lib -static -static-libgcc -static-libstdc++" \
        --extra-libs="-Wl,--start-group -lstdc++ -lgcc -lc -Wl,--end-group" \
        --pkg-config-flags="--static" \
        --enable-static --disable-shared \
        --enable-gpl --enable-version3 \
        --enable-libsrt \
        --enable-ffmpeg \
        --disable-doc --disable-debug --disable-ffplay --disable-ffprobe \
        --disable-avdevice --disable-postproc --disable-avfilter \
        --disable-everything \
        --enable-protocol=rtsp,tcp,udp,srt,file \
        --enable-demuxer=rtsp,rtp \
        --enable-muxer=mpegts,rtsp \
        --enable-parser=h264,hevc,aac \
        --enable-decoder=aac \
        --enable-bsf=h264_mp4toannexb \
        --enable-runtime-cpudetect \
     || (echo "--- ffbuild/config.log (tail -n 200) ---"; tail -n 200 ffbuild/config.log; false)) \
    && make -j"$(nproc)"

RUN mkdir -p /out && cp /src/ffmpeg/ffmpeg /out/ffmpeg_armv7 && \
    $CROSS_TRIPLE-strip /out/ffmpeg_armv7

FROM scratch AS export
COPY --from=build /out/ffmpeg_armv7 /ffmpeg_armv7
