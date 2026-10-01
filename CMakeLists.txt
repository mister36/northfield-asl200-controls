cmake_minimum_required(VERSION 3.16)
project(asl200_controls C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(ASL200_WERROR "Treat warnings as errors" ON)
set(ASL200_VARIANT "asl200_diesel_autocar" CACHE STRING "Variant for the target firmware image")

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(GEN_DIR ${CMAKE_BINARY_DIR}/generated)
file(GLOB VARIANT_FILES CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/variants/asl200_*.yaml)
set(VARIANTS "")
set(GEN_OUTPUTS ${GEN_DIR}/params_types.h)
foreach(f ${VARIANT_FILES})
  get_filename_component(v ${f} NAME_WE)
  list(APPEND VARIANTS ${v})
  list(APPEND GEN_OUTPUTS ${GEN_DIR}/params_${v}.h ${GEN_DIR}/params_${v}.json)
endforeach()

add_custom_command(
  OUTPUT ${GEN_OUTPUTS}
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/codegen/gen_params.py --out ${GEN_DIR}
  DEPENDS ${VARIANT_FILES} ${CMAKE_SOURCE_DIR}/variants/common.yaml ${CMAKE_SOURCE_DIR}/variants/schema.json
          ${CMAKE_SOURCE_DIR}/codegen/gen_params.py ${CMAKE_SOURCE_DIR}/codegen/variant_loader.py
  COMMENT "Generating variant parameter headers"
  VERBATIM)
add_custom_target(asl200_params DEPENDS ${GEN_OUTPUTS})

set(WARN_FLAGS -Wall -Wextra -Wpedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wdouble-promotion)
if(ASL200_WERROR)
  list(APPEND WARN_FLAGS -Werror)
endif()

add_library(asl200_core STATIC
  firmware/src/can_io.c
  firmware/src/controller.c
  firmware/src/faults.c
  firmware/src/filters.c
  firmware/src/interlocks.c
  firmware/src/scaling.c)
add_dependencies(asl200_core asl200_params)
target_include_directories(asl200_core PUBLIC firmware/include ${GEN_DIR})
target_compile_options(asl200_core PRIVATE ${WARN_FLAGS})
set_target_properties(asl200_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
if(NOT CMAKE_CROSSCOMPILING)
  target_link_libraries(asl200_core PUBLIC m)
endif()

if(CMAKE_CROSSCOMPILING)
  add_executable(asl200_fw firmware/target/main.c)
  target_compile_definitions(asl200_fw PRIVATE PARAMS_HEADER="params_${ASL200_VARIANT}.h")
  target_compile_options(asl200_fw PRIVATE ${WARN_FLAGS})
  target_link_libraries(asl200_fw PRIVATE asl200_core m)
  set_target_properties(asl200_fw PROPERTIES OUTPUT_NAME asl200_fw_${ASL200_VARIANT} SUFFIX .elf)
  add_custom_command(TARGET asl200_fw POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:asl200_fw> ${CMAKE_BINARY_DIR}/asl200_fw_${ASL200_VARIANT}.hex
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:asl200_fw>)
  return()
endif()

# Host build: one SIL shared library per variant, consumed by sil/ via ctypes.
foreach(v ${VARIANTS})
  add_library(asl200_sil_${v} SHARED firmware/sil/sil_api.c)
  target_compile_definitions(asl200_sil_${v} PRIVATE PARAMS_HEADER="params_${v}.h")
  target_compile_options(asl200_sil_${v} PRIVATE ${WARN_FLAGS})
  target_link_libraries(asl200_sil_${v} PRIVATE asl200_core)
  set_target_properties(asl200_sil_${v} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/sil
    C_VISIBILITY_PRESET hidden)
endforeach()

# Host compile check of the target entry point (never run).
add_executable(asl200_fw_hostcheck firmware/target/main.c)
target_compile_definitions(asl200_fw_hostcheck PRIVATE PARAMS_HEADER="params_${ASL200_VARIANT}.h")
target_compile_options(asl200_fw_hostcheck PRIVATE ${WARN_FLAGS})
target_link_libraries(asl200_fw_hostcheck PRIVATE asl200_core)

enable_testing()
foreach(t test_scaling test_filters test_interlocks test_can_io)
  add_executable(${t} tests/unit/${t}.c)
  target_compile_definitions(${t} PRIVATE PARAMS_HEADER="params_asl200_diesel_autocar.h")
  target_compile_options(${t} PRIVATE ${WARN_FLAGS})
  target_link_libraries(${t} PRIVATE asl200_core)
  add_test(NAME ${t} COMMAND ${t})
endforeach()
