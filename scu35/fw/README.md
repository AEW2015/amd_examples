# Application source

`bench.c` is the **canonical complete application** compiled by `lab.py build --phase firmware`. Edit it to change user payloads, iterations or demonstrations; the linker layout is `lscript.ld`.

`bench_body.c`, `features.c` and `timer_io.c` are retained readable reference fragments for the presentation. They are already incorporated into `bench.c` and are not separate build inputs. `vendor/hss.c` preserves the pinned original AMD public-vector example and its license. No old generator or BSP workspace is needed.

Keep firmware-owned shared memory inside `0x0402b000..0x0402dfff`, keep all loadable bytes inside the 128 KiB PL BRAM, and keep correctness checks outside the measured interval. Changes require a new ELF/PDI build, new hashes and a new hardware capture before reporting fresh timings.
