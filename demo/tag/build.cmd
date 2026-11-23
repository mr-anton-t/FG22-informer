@echo off
setlocal
set ROOT=%~dp0
set GCC=%ROOT%..\..\tools\gcc\xpack-arm-none-eabi-gcc-13.3.1-1.1\bin\arm-none-eabi-gcc.exe
set OBJCOPY=%ROOT%..\..\tools\gcc\xpack-arm-none-eabi-gcc-13.3.1-1.1\bin\arm-none-eabi-objcopy.exe
if not exist "%GCC%" (
  echo Compiler missing: %GCC%
  exit /b 1
)
if "%ENABLE_PORT%"=="" set ENABLE_PORT=2
if "%ENABLE_PIN%"=="" set ENABLE_PIN=7
"%GCC%" -mcpu=cortex-m33 -mthumb -mfloat-abi=soft -Os -ffreestanding -nostdlib -fno-builtin -Wall -Wextra -DENABLE_PORT=%ENABLE_PORT% -DENABLE_PIN=%ENABLE_PIN% -T "%ROOT%link.ld" -o "%ROOT%test.elf" "%ROOT%main.c"
if errorlevel 1 exit /b 1
"%OBJCOPY%" -O ihex "%ROOT%test.elf" "%ROOT%test.hex"
if errorlevel 1 exit /b 1
echo Built %ROOT%test.hex
