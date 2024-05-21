#include <LiquidCrystal.h>
#include <stdio.h>
#include <stdint.h>
#include <SPI.h>

#define ZERO_VOLT 32768
#define FIVE_VOLT 49151

// Define macros for compressing sequential bytes read from the serial port into long and short ints
#define makeUnsignedShort(msb, lsb) ((msb << 8) | (lsb))

// Trigger line level configuration. This defines the logic level when the trigger is activated.
// The optoisolator in Pulse Pal 2 is inverting, so its output is high by default, and becomes low 
// when voltage is applied to the trigger channel. Set this to 1 if using a non-inverting isolator.
#define TriggerLevel 0

// initialize Arduino LCD library with the numbers of the interface pins
LiquidCrystal lcd(10, 9, 8, 7, 6, 5);

// Variables that define other hardware pins
byte TriggerLines[2] = {12,11}; // Trigger channels 1 and 2
byte InputLEDLines[2] = {13, A0}; // LEDs above trigger channels 1-2. An = Arduino Analog Channel n.
byte OutputLEDLines[4] = {A1,A7,A11,A10}; // LEDs above output channels 1-4

byte SyncPin=44; // AD5724 Pin 7 (Sync)
byte LDACPin=A2; // AD5724 Pin 10 (LDAC)
byte SDChipSelect=14; // microSD CS Pin 

// Variables for SPI bus
SPISettings DACSettings(25000000, MSBFIRST, SPI_MODE2); // Settings for DAC

// The following are volts in bits. 16 bits span -10V to +10V.
uint16_t RestingVoltage[4] = {0}; // Voltage the system returns to between pulses (0 bits = 0V)

// The following are single byte parameters
byte OpMenuByte = 213; // This byte must be the first byte in any serial transmission to Pulse Pal. Reduces the probability of interference from port-scanning software

boolean SerialReadTimedout = 0; // Goes to 1 if a serial read timed out, causing all subsequent serial reads to skip until next main loop iteration.
int SerialCurrentTime = 0; // Current time (millis) for serial read timeout
int SerialReadStartTime = 0; // Time the serial read was started
int Timeout = 500; // Times out after 500ms

// Variables used in stimulus playback
byte inByte; byte inByte2; byte CommandByte;
boolean InputValues[2] = {0}; // The values read directly from the two inputs (for analog, digital equiv. after thresholding)

// variables used in thumb joystick menus
char centeredText[16] = {0}; // Global for returning centered text to display on a 16-char screen line
byte fileNameOffset = 0; // Offset of centered string (for display on 16-char screen)
char tempText[16] = {0}; // Temporary buffer for holding a file name or other text
boolean NeedUpdate = 0; // If a new menu item is selected, the screen must be updated

// Other variables
boolean DACFlags[4] = {0}; // Flag to indicate whether each output channel needs to be updated in a call to dacWrite()
byte dacBuffer[3] = {0}; // Holds bytes about to be written via SPI (for improved transfer speed with array writes)
union {
    byte byteArray[8];
    uint16_t uint16[4];
} dacValue; // Union allows faster type conversion between 16-bit DAC values and bytes to write via SPI

volatile bool input_channel_1_curr=0;
volatile bool input_channel_2_curr = true;
uint16_t volt_value = 0;

unsigned long pulse_dur = 50; // duration of pulse in milliseconds
unsigned long trial_timer = 0;
unsigned long reward_timer = 0;

void setup() {
  pinMode(SyncPin, OUTPUT); // Configure SPI bus pins as outputs
  pinMode(LDACPin, OUTPUT);
  SPI.begin();
  SPI.beginTransaction(DACSettings);
  digitalWriteDirect(LDACPin, LOW);
  ProgramDAC(12, 0, 4); // Set DAC output range to +/- 10V    DAC chip used here is the AD5754
  // Set DAC to resting voltage on all channels
  for (int i = 0; i < 4; i++) {
    RestingVoltage[i] = 0; // 16-bit code for 0, 
    dacValue.uint16[i] = RestingVoltage[i];
    DACFlags[i] = 1; // DACFlags must be set to 1 on each channel, so the channels aren't skipped in dacWrite()
  }
  RestingVoltage[1] = 55049; // 4.2V
  dacValue.uint16[1] = RestingVoltage[1];
  ProgramDAC(16, 0, 31); // Power up DACs
  dacWrite(); // Update the DAC
  SerialUSB.begin(115200); // Initialize Serial USB interface at 115.2kbps
  // set up the LCD
  lcd.begin(16, 2);
  lcd.clear();
  lcd.home();
  lcd.noDisplay();
  delay(100);
  lcd.display();

  // Pin modes
  pinMode(TriggerLines[0], INPUT); // Configure trigger pins as digital inputs
  pinMode(TriggerLines[1], INPUT);

  for (int x = 0; x < 4; x++) {
    pinMode(OutputLEDLines[x], OUTPUT); // Configure channel LED pins as outputs
    digitalWrite(OutputLEDLines[x], LOW); // Initialize channel LEDs to low (off)
  }
  pinMode(SDChipSelect, OUTPUT);

  for (int x = 0; x < 2; x++) {
    pinMode(InputLEDLines[x], OUTPUT);
    digitalWrite(InputLEDLines[x], LOW);
  }

  write2Screen(" Institute of", "Physiology-1");
}

void loop() {
  // Writing only input LEDs
  for (int x = 0; x < 2; x++) {
    InputValues[x] = digitalReadDirect(TriggerLines[x]);
    if (InputValues[x] == TriggerLevel) {
      digitalWrite(InputLEDLines[x], HIGH);
    } else {
      digitalWrite(InputLEDLines[x], LOW);
    }
  }
  // Lick sensor
  bool lick = digitalReadDirect(TriggerLines[0]);
  if (lick != input_channel_1_curr) {
    input_channel_1_curr = lick;
    if (input_channel_1_curr == TriggerLevel) {
      dacValue.uint16[0] = 65535;
      digitalWrite(OutputLEDLines[0], HIGH);
    } else {
      dacValue.uint16[0] = 0;
      digitalWrite(OutputLEDLines[0], LOW);
    }
    DACFlags[0] = 1;
  } else {
    DACFlags[0] = 0;
  }
  // Frame Pulse
  bool frame = digitalReadDirect(TriggerLines[1]); // trigger channel 2 for frames
  if (frame != input_channel_2_curr) {
    input_channel_2_curr = frame;
    if (input_channel_2_curr == TriggerLevel) {
      digitalWrite(OutputLEDLines[0], HIGH);
    } else {
      digitalWrite(OutputLEDLines[0], LOW);
    }
  }
  // Turn off pulses
  if ((millis() > (trial_timer + pulse_dur)) & (dacValue.uint16[0] != (uint16_t) ZERO_VOLT)) {
    dacValue.uint16[0] = (uint16_t) ZERO_VOLT;
    DACFlags[0] = true;
  }
  if ((millis() > (reward_timer + pulse_dur)) & (dacValue.uint16[2] != (uint16_t) ZERO_VOLT)) {
    dacValue.uint16[2] = (uint16_t) ZERO_VOLT;
    DACFlags[2] = true;
  }

  if (SerialUSB.available()) { // If bytes are available in the serial port buffer
    CommandByte = SerialUSB.read(); // Read a byte
    if (CommandByte == OpMenuByte) { // The first byte must be 213. Now, read the actual command byte. (Reduces interference from port scanning applications)
      CommandByte = SerialUSB.read(); // Read a byte
      
      if (CommandByte == 0x01) { // output channel 2 position
        volt_value = SerialReadShort();
        if (volt_value != dacValue.uint16[1]) {
          dacValue.uint16[1] = (uint16_t) volt_value;
          DACFlags[1] = 1;
        }
      }
      if (CommandByte == 0x02) { // read frame pulse
        SerialUSB.write((int) !input_channel_2_curr); // trigger channels are inverting (i.e. low is high and high is low, stupid.....)
      }
      if (CommandByte == 0x03) { // read lick value
        SerialUSB.write((int) !input_channel_1_curr);
      }
      if (CommandByte == 0x04) { // pulse trial
        trial_timer = millis();
        dacValue.uint16[0] = (uint16_t) FIVE_VOLT;
        DACFlags[0] = true;
      }
      if (CommandByte == 0x05) { // pulse reward
        reward_timer = millis();
        dacValue.uint16[2] = (uint16_t) FIVE_VOLT;
        DACFlags[2] = true;
      }
      if (CommandByte == 0x06) { // brake
        bool state = (bool) SerialReadByte();
        if (state) {
          dacValue.uint16[3] = (uint16_t) FIVE_VOLT;
        } else {
          dacValue.uint16[3] = (uint16_t) ZERO_VOLT;
        }
        DACFlags[3] = true;
      }
    }
  }
  dacWrite();
}

uint16_t SerialReadShort() {
  // Generic routine for getting a 2-byte unsigned int over the serial port
  unsigned long MyOutput = 0;
  inByte = SerialReadByte();
  inByte2 = SerialReadByte();
  MyOutput = makeUnsignedShort(inByte2, inByte);
  return MyOutput;
}

void dacWrite() {
  digitalWriteDirect(LDACPin, HIGH);
  for (int i = 0; i < 4; i++) {
    if (DACFlags[i]) {
      digitalWriteDirect(SyncPin, LOW);
      dacBuffer[0] = i;
      dacBuffer[1] = dacValue.byteArray[1 + (i * 2)];
      dacBuffer[2] = dacValue.byteArray[0 + (i * 2)];
      SPI.transfer(dacBuffer, 3);
      digitalWriteDirect(SyncPin, HIGH);
      DACFlags[i] = 0;
    }
  }
  digitalWriteDirect(LDACPin, LOW);
}

void ProgramDAC(byte Data1, byte Data2, byte Data3) {
  digitalWriteDirect(LDACPin, HIGH);
  digitalWriteDirect(SyncPin, LOW);
  SPI.transfer(Data1);
  SPI.transfer(Data2);
  SPI.transfer(Data3);
  digitalWriteDirect(SyncPin, HIGH);
  digitalWriteDirect(LDACPin, LOW);
}

void digitalWriteDirect(int pin, boolean val) {
  if (val) g_APinDescription[pin].pPort -> PIO_SODR = g_APinDescription[pin].ulPin;
  else g_APinDescription[pin].pPort -> PIO_CODR = g_APinDescription[pin].ulPin;
}

byte digitalReadDirect(int pin) {
  return !!(g_APinDescription[pin].pPort -> PIO_PDSR & g_APinDescription[pin].ulPin);
}

void centerText(char myText[]) {
  byte spaceCounter = 0;
  for (int i = 0; i < 16; i++) {
    if (myText[i] == 0) {
      spaceCounter++;
    }
    tempText[i] = 32;
  }
  fileNameOffset = spaceCounter / 2;
  for (int i = fileNameOffset; i < 16; i++) {
    tempText[i] = myText[i - fileNameOffset];
  }
  for (int i = 0; i < 16; i++) {
    centeredText[i] = tempText[i];
  }
}

byte SerialReadByte() {
  byte ReturnByte = 0;
  if (SerialReadTimedout == 0) {
    SerialReadStartTime = millis();
    while (SerialUSB.available() == 0) {
      SerialCurrentTime = millis();
      if ((SerialCurrentTime - SerialReadStartTime) > Timeout) {
        SerialReadTimedout = 1;
        return 0;
      }
    }
    ReturnByte = SerialUSB.read();
    return ReturnByte;
  } else {
    return 0;
  }
}

void write2Screen(const char * Line1,
  const char * Line2) {
  lcd.clear();
  lcd.home();
  lcd.print(Line1);
  lcd.setCursor(0, 1);
  lcd.print(Line2);
}
