
#include <LiquidCrystal.h>
#include "DueTimer.h"
#include <stdio.h>
#include <stdint.h>
#include <SPI.h>

#define ZERO_VOLT 0;
#define FIVE_VOLT 65530;

// Define macros for compressing sequential bytes read from the serial port into long and short ints
#define makeUnsignedLong(msb, byte2, byte3, lsb) ((msb << 24) | (byte2 << 16) | (byte3 << 8) | (lsb))
#define makeUnsignedShort(msb, lsb) ((msb << 8) | (lsb))

// Trigger line level configuration. This defines the logic level when the trigger is activated.
// The optoisolator in Pulse Pal 2 is inverting, so its output is high by default, and becomes low 
// when voltage is applied to the trigger channel. Set this to 1 if using a non-inverting isolator.
#define TriggerLevel 0



// initialize Arduino LCD library with the numbers of the interface pins
LiquidCrystal lcd(10, 9, 8, 7, 6, 5);
bool pump_prev = 0;
bool pump_curr = 0;
// Variables that define other hardware pins
byte TriggerLines[2] = {12,11}; // Trigger channels 1 and 2
byte InputLEDLines[2] = {13, A0}; // LEDs above trigger channels 1-2. An = Arduino Analog Channel n.
byte OutputLEDLines[4] = {A1,A7,A11,A10}; // LEDs above output channels 1-4

byte SyncPin=44; // AD5724 Pin 7 (Sync)
byte LDACPin=A2; // AD5724 Pin 10 (LDAC)
byte SDChipSelect=14; // microSD CS Pin 

// Variables for SPI bus
SPISettings DACSettings(25000000, MSBFIRST, SPI_MODE2); // Settings for DAC

// Parameters that define pulse trains currently loaded on the 4 output channels
// For a visual description of these parameters, see https://sites.google.com/site/pulsepalwiki/parameter-guide
// The following parameters are times in microseconds:

// The following are volts in bits. 16 bits span -10V to +10V.
uint16_t Phase1Voltage[4] = {0}; // The pulse voltage in monophasic mode, and phase 1 voltage in biphasic mode
uint16_t Phase2Voltage[4] = {0}; // Phase 2 voltage in biphasic mode.
uint16_t RestingVoltage[4] = {0}; // Voltage the system returns to between pulses (0 bits = 0V)
// The following are single byte parameters

byte OpMenuByte = 213; // This byte must be the first byte in any serial transmission to Pulse Pal. Reduces the probability of interference from port-scanning software

boolean SerialReadTimedout = 0; // Goes to 1 if a serial read timed out, causing all subsequent serial reads to skip until next main loop iteration.
int SerialCurrentTime = 0; // Current time (millis) for serial read timeout
int SerialReadStartTime = 0; // Time the serial read was started
int Timeout = 500; // Times out after 500ms
byte BrokenBytes[4] = {0}; // Used to store sequential bytes when converting bytes to short and long ints

// Variables used in stimulus playback
byte inByte; byte inByte2; byte inByte3; byte inByte4; byte CommandByte;
byte LogicLevel = 0;
unsigned long LastLoopTime = 0;
byte PulseStatus[4] = {0}; // This is 0 if not delivering a pulse, 1 if phase 1, 2 if inter phase interval, 3 if phase 2.
boolean BurstStatus[4] = {0}; // This is "true" during bursts and false during inter-burst intervals.
boolean StimulusStatus[4] = {0}; // This is "true" for a channel when the stimulus train is actively being delivered
boolean PreStimulusStatus[4] = {0}; // This is "true" for a channel during the pre-stimulus delay
boolean InputValues[2] = {0}; // The values read directly from the two inputs (for analog, digital equiv. after thresholding)
boolean InputValuesLastCycle[2] = {0}; // The values on the last cycle. Used to detect low to high transitions.
byte LineTriggerEvent[2] = {0}; // 0 if no line trigger event detected, 1 if low-to-high, 2 if high-to-low.
unsigned long InputLineDebounceTimestamp[2] = {0}; // Last time the line went from high to low
boolean UsesBursts[4] = {0};
unsigned long PulseDuration[4] = {0}; // Duration of a pulse (sum of 3 phases for biphasic pulse)
boolean IsBiphasic[4] = {0};
boolean IsCustomBurstTrain[4] = {0};
boolean ContinuousLoopMode[4] = {0}; // If true, the channel loops its programmed stimulus train continuously
byte StimulatingState = 0; // 1 if ANY channel is stimulating, 2 if this is the first cycle after the system was triggered. 
byte LastStimulatingState = 0;
boolean WasStimulating = 0; // true if any channel was stimulating on the previous loop. Used to force a DAC write after all channels end their stimulation, to return lines to 0
int nStimulatingChannels = 0; // number of actively stimulating channels
boolean DACFlag = 0; // true if any DAC channel needs to be updated
byte DefaultInputLevel = 0; // 0 for PulsePal 0.3, 1 for 0.2 and 0.1. Logic is inverted by optoisolator

// SD variables
//const size_t BUF_SIZE = 1;
uint8_t buf[1];
uint8_t buf2[2];
uint8_t buf4[4];

byte ClickerButtonLine = 15; // Digital line that reports the thumb joystick click state
String currentSettingsFileName = "default.pps"; // Filename is a string so it can be easily resized
byte settingsFileNameLength = 0; // Set when a new file name is entered
char currentSettingsFileNameChar[100]; // Filename must be converted from string to character array for use with sdFAT
char candidateSettingsFileChar[16];
byte settingsOp = 0; // Reports whether to load an existing settings file, or create/overwrite, or delete
byte validProgram = 0; // Reports whether the program just loaded from the SD card is valid 
uint16_t myFilePos = 2; // Index of current file position in folder. 0 and 1 are . and ..

// variables used in thumb joystick menus
char Value2Display[18] = {' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '\0'}; // Holds text for sprintf
int ScrollSpeedDelay = 200000; // Microseconds before scrolling values while joystick is held in one direction
byte CursorPos = 0;
byte CursorPosRightLimit = 0;
byte CursorPosLeftLimit = 0;
byte ValidCursorPositions[9] = {0};
int Digits[9] = {0};
unsigned int DACBits = pow(2,16);
float CandidateVoltage = 0; // used to see if voltage will go over limits for DAC
float FractionalVoltage = 0;
unsigned long CursorToggleTimer = 0; 
unsigned long CursorToggleThreshold = 20000;
boolean CursorOn = 0;
int ClickerX = 0; // Value of analog reads from X line of joystick input device
int ClickerY = 0; // Value of analog reads from Y line of joystick input device
int ClickerMinThreshold = 300; // Joystick position to consider an upwards or leftwards movement (on Y and X lines respectively)
int ClickerMaxThreshold = 700;
boolean ClickerButtonState = 0; // Value of digital reads from button line of joystick input device
boolean LastClickerButtonState = 0;
unsigned int DebounceTime = 0; // Time since the joystick button changed states
int LastClickerYState = 0; // 0 for neutral, 1 for up, 2 for down.
int LastClickerXState = 0; // 0 for neutral, 1 for left, 2 for right.
int inMenu = 0; // Menu level: 0 for top, 1 for channel menu, 2 for action menu
int SelectedChannel = 0; // Channel the user has selected
int SelectedAction = 1; // Action the user has selected
byte isNegativeZero = 0; // Keeps track of negative zero in digit-wise voltage adjustment menu
byte SelectedInputAction = 1; // Trigger channel action the user has selected
int SelectedStimMode = 1; // Manual trigger from joystick menu. 1 = Single train, 2 = Single pulse, 3 = continuous stimulation
int lastDebounceTime = 0; // to debounce the joystick button
boolean lastButtonState = 0; // last logic state of joystick button
boolean ChoiceMade = 0; // determines whether user has chosen a value from a list
unsigned int UserValue = 0; // The current value displayed on a list of values (written to LCD when choosing parameters)
char CommanderString[16] = " PULSE PAL v2.0"; // Displayed at the menu top when disconnected from software
char DefaultCommanderString[16] = " PULSE PAL v2.0"; // The CommanderString can be overwritten. This stores the original.
char ClientStringSuffix[11] = " Connected"; // Displayed after 6-character client ID string (as in, "MATLAB Connected")
char centeredText[16] = {0}; // Global for returning centered text to display on a 16-char screen line
byte fileNameOffset = 0; // Offset of centered string (for display on 16-char screen)
char tempText[16] = {0}; // Temporary buffer for holding a file name or other text
boolean NeedUpdate = 0; // If a new menu item is selected, the screen must be updated

// Screen saver variables
boolean useScreenSaver = 0; // Disabled by default
boolean SSactive = 0; // Bit indicating whether screen saver is currently active
unsigned long SSdelay = 60000; // Idle cycles until screen saver is activated
unsigned long SScount = 0; // Counter of idle cycles

// Other variables
int ConnectedToApp = 0; // 0 if disconnected, 1 if connected
byte CycleDuration = 50; // in microseconds, time between hardware cycles (each cycle = read trigger channels, update output channels)
unsigned int CycleFrequency = 20000; // in Hz, same idea as CycleDuration
void handler(void);
boolean SoftTriggered[4] = {0}; // If a software trigger occurred this cycle (for timing reasons, it is scheduled to occur on the next cycle)
boolean SoftTriggerScheduled[4] = {0}; // If a software trigger is scheduled for the next cycle
unsigned long callbackStartTime = 0;
boolean DACFlags[4] = {0}; // Flag to indicate whether each output channel needs to be updated in a call to dacWrite()
byte dacBuffer[3] = {0}; // Holds bytes about to be written via SPI (for improved transfer speed with array writes)
union {
    byte byteArray[8];
    uint16_t uint16[4];
} dacValue; // Union allows faster type conversion between 16-bit DAC values and bytes to write via SPI

volatile bool input_channel_1_curr=0;
uint16_t volt_value = 0;
long LAST_PING=0;
void setup() {
  LAST_PING = micros();
  pinMode(SyncPin, OUTPUT); // Configure SPI bus pins as outputs
  pinMode(LDACPin, OUTPUT);
  SPI.begin();
  SPI.beginTransaction(DACSettings);
  digitalWriteDirect(LDACPin, LOW);
  ProgramDAC(12, 0, 0); // Set DAC output range to +/- 10V   0 for unipolar 5v
  // Set DAC to resting voltage on all channels
  for (int i = 0; i < 4; i++) {
    RestingVoltage[i] = 0; // 16-bit code for 0, 
    dacValue.uint16[i] = RestingVoltage[i];
    DACFlags[i] = 1; // DACFlags must be set to 1 on each channel, so the channels aren't skipped in dacWrite()
  }
   RestingVoltage[1] = 55049;                 // 4.2V
   dacValue.uint16[1] = RestingVoltage[1];
  ProgramDAC(16, 0, 31); // Power up DACs
  dacWrite(); // Update the DAC
  SerialUSB.begin(115200); // Initialize Serial USB interface at 115.2kbps
  // set up the LCD
  lcd.begin(16, 2);
  lcd.clear();
  lcd.home();
  lcd.noDisplay() ;
  delay(100);
  lcd.display() ;
  
  // Pin modes
  pinMode(TriggerLines[0], INPUT); // Configure trigger pins as digital inputs
  pinMode(TriggerLines[1], INPUT);
  pinMode(ClickerButtonLine, INPUT_PULLUP); // Configure clicker button as digital input with an internal pullup resistor
 
  for (int x = 0; x < 4; x++) {
    pinMode(OutputLEDLines[x], OUTPUT); // Configure channel LED pins as outputs
    digitalWrite(OutputLEDLines[x], LOW); // Initialize channel LEDs to low (off)
  }
    pinMode(SDChipSelect, OUTPUT);
 
    
    for (int x = 0; x < 2; x++) {
      pinMode(InputLEDLines[x], OUTPUT);
      digitalWrite(InputLEDLines[x], LOW);
    }



    write2Screen(" Institute of","Physiology-1" );
    Timer3.attachInterrupt(handler);
    Timer3.start(500*1000); 
}

void loop() {
  LAST_PING = micros();


  // Pump button
  ClickerButtonState = ReadDebouncedButton();
  if (ClickerButtonState==1 && LastClickerButtonState==0){
    pump_curr = 1;
    LastClickerButtonState=1;
  }

  if (ClickerButtonState==0 && LastClickerButtonState==1){
    pump_curr = 0;
    LastClickerButtonState=0;
  }
  
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
 if (lick != input_channel_1_curr){
  input_channel_1_curr = lick;
  if(input_channel_1_curr == TriggerLevel){
      dacValue.uint16[0] = 65535;
      digitalWrite(OutputLEDLines[0], HIGH);
    }
    else{
      dacValue.uint16[0] = 0;
      digitalWrite(OutputLEDLines[0], LOW);
    }     
  DACFlags[0] = 1;
 }
 else{
  DACFlags[0] = 0;
 }
    
  if (SerialUSB.available()) { // If bytes are available in the serial port buffer
    CommandByte = SerialUSB.read(); // Read a byte
    if (CommandByte == OpMenuByte) { // The first byte must be 213. Now, read the actual command byte. (Reduces interference from port scanning applications)
       CommandByte = SerialUSB.read(); // Read a byte
    if (CommandByte == 0x01){
      volt_value = SerialReadShort();
      if (volt_value != dacValue.uint16[1]){
        dacValue.uint16[1] = (uint16_t)volt_value;
        DACFlags[1] = 1;
        digitalWrite(OutputLEDLines[1], HIGH);
      }
    }
    if (CommandByte == 0x02){
      pump_curr = (bool)SerialUSB.read();
    }
    if (CommandByte == 0x03){
      //SerialUSB.flush();
      SerialUSB.write((int) !input_channel_1_curr+ 2*pump_curr);
    }
      
    }
  }

  if(pump_prev!=pump_curr){
        DACFlags[2] = 1;
        pump_prev = pump_curr;
        if (pump_curr==0){
          dacValue.uint16[2] = ZERO_VOLT;
          digitalWrite(OutputLEDLines[2], LOW);
        }
        else{
          dacValue.uint16[2] = FIVE_VOLT;
          digitalWrite(OutputLEDLines[2], HIGH);
        }
      }
  
//  while(SerialUSB.available()){
//    SerialUSB.read();
//  }
  
  
  dacWrite();
//SerialWriteLong(volt_value);
//delayMicroseconds(500);  // 500 us
   
}

void handler(void) {                     
if (micros()- LAST_PING > 5*1000){
  //Software_Reset();
}

}

unsigned long SerialReadLong() {
   // Generic routine for getting a 4-byte long int over the serial port
   unsigned long OutputLong = 0;
          inByte = SerialUSB.read();
          inByte2 = SerialUSB.read();
          inByte3 = SerialUSB.read();
          inByte4 = SerialUSB.read();
          OutputLong =  makeUnsignedLong(inByte4, inByte3, inByte2, inByte);
  return OutputLong;
}

uint16_t SerialReadShort() {
   // Generic routine for getting a 2-byte unsigned int over the serial port
   unsigned long MyOutput = 0;
          inByte = SerialReadByte();
          inByte2 = SerialReadByte();
          MyOutput =  makeUnsignedShort(inByte2, inByte);
  return MyOutput;
}

byte* Long2Bytes(long LongInt2Break) {
  byte Output[4] = {0};
  return Output;
}



void dacWrite() {
  digitalWriteDirect(LDACPin,HIGH);
  for (int i = 0; i<4; i++) {
    if (DACFlags[i]) {
      digitalWriteDirect(SyncPin,LOW);
      dacBuffer[0] = i;
      dacBuffer[1] = dacValue.byteArray[1+(i*2)];
      dacBuffer[2] = dacValue.byteArray[0+(i*2)];
      SPI.transfer(dacBuffer,3);
      digitalWriteDirect(SyncPin,HIGH);
      DACFlags[i] = 0;
    }
  }
  digitalWriteDirect(LDACPin,LOW);
}

void ProgramDAC(byte Data1, byte Data2, byte Data3) {
  digitalWriteDirect(LDACPin,HIGH);
  digitalWriteDirect(SyncPin,LOW);
  SPI.transfer (Data1);
  SPI.transfer (Data2);
  SPI.transfer (Data3);
  digitalWriteDirect(SyncPin,HIGH);
  digitalWriteDirect(LDACPin,LOW);
}

void digitalWriteDirect(int pin, boolean val){
  if(val) g_APinDescription[pin].pPort -> PIO_SODR = g_APinDescription[pin].ulPin;
  else    g_APinDescription[pin].pPort -> PIO_CODR = g_APinDescription[pin].ulPin;
}

byte digitalReadDirect(int pin){
  return !!(g_APinDescription[pin].pPort -> PIO_PDSR & g_APinDescription[pin].ulPin);
}



void centerText(char myText[]) {
  byte spaceCounter = 0;
  for (int i = 0; i < 16; i++) {
    if (myText[i] == 0) {spaceCounter++;}
    tempText[i] = 32;
  }
  fileNameOffset = spaceCounter/2;
    for (int i = fileNameOffset; i < 16; i++) {
      tempText[i] = myText[i-fileNameOffset];
    }
    for (int i = 0; i < 16; i++) {
      centeredText[i] = tempText[i];
    }
}









byte SerialReadByte(){
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







void write2Screen(const char* Line1, const char* Line2) {
  lcd.clear(); lcd.home(); lcd.print(Line1); lcd.setCursor(0, 1); lcd.print(Line2);
}

void breakLong(unsigned long LongInt2Break) {
  //BrokenBytes is a global array for the output of long int break operations
  BrokenBytes[3] = (byte)(LongInt2Break >> 24);
  BrokenBytes[2] = (byte)(LongInt2Break >> 16);
  BrokenBytes[1] = (byte)(LongInt2Break >> 8);
  BrokenBytes[0] = (byte)LongInt2Break;
}

void breakShort(word Value2Break) {
  //BrokenBytes is a global array for the output of long int break operations
  BrokenBytes[1] = (byte)(Value2Break >> 8);
  BrokenBytes[0] = (byte)Value2Break;
}
  

void SerialWriteLong(unsigned long num) {
  SerialUSB.write((byte)num); 
  SerialUSB.write((byte)(num >> 8)); 
  SerialUSB.write((byte)(num >> 16)); 
  SerialUSB.write((byte)(num >> 24));
}

void SerialWriteShort(word num) {
  SerialUSB.write((byte)num); 
  SerialUSB.write((byte)(num >> 8)); 
}

boolean ReadDebouncedButton() {
  DebounceTime = millis();
  ClickerButtonState = digitalRead(ClickerButtonLine);
    if (ClickerButtonState != lastButtonState) {lastDebounceTime = DebounceTime;}
    lastButtonState = ClickerButtonState;
   if (((DebounceTime - lastDebounceTime) > 75) && (ClickerButtonState == 0)) {
      return 1;
   } else {
     return 0;
   }
}

void Software_Reset() {
  const int RSTC_KEY = 0xA5;
  RSTC->RSTC_CR = RSTC_CR_KEY(RSTC_KEY) | RSTC_CR_PROCRST | RSTC_CR_PERRST;
  while (true);
}
