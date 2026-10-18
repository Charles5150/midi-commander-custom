--[[
MIDI Commander Custom: the song and the part you are in, on the pedal's display.

The region under the play cursor (the edit cursor when stopped) names the song,
written across the pedal's top line until the next song. A marker passed while
playing names the part, shown over it for a moment: "Chorus", "Solo". With no
region the project's name stands for the song, for one project per song.

Optionally, play, record, repeat and the metronome go out as CCs, 127 when on
and 0 when off, so a toggle button sending the same CC lights with them
(LED_Feedback on in the pedal's configuration).

Run it once from Actions > Show action list > New action > Load ReaScript; it
keeps running, and running it again stops it. In a toolbar button it lights
while it runs. Tried on REAPER 7.79. Needs the pedal's output ticked as
Enabled in Preferences > Audio > MIDI Inputs/Outputs, and the pedal's
firmware 0.46 or later (0.61 for a name longer than its place to scroll).

https://github.com/Charles5150/midi-commander-custom
]]

-- Settings ------------------------------------------------------------------

-- Part of the name of the pedal's output in REAPER's MIDI devices
local DEVICE = "MIDI Commander"
-- Where the song goes: "line" (11 large letters), "small" (18 small ones),
-- "name" (4 large, in place of the bank name) or "info" (11 small, beside it)
local SONG_PLACE = "line"
-- Where a marker's name shows for a moment, or nil to leave markers out
local PART_PLACE = "line"
-- The project's name when the cursor is in no region; false for nothing,
-- which gives the line back to the bank
local PROJECT_NAME_AS_SONG = true
-- The CCs for the transport, nil for none; channel 1-16
local CC_CHANNEL = 16
local CC_PLAY = nil
local CC_RECORD = nil
local CC_REPEAT = nil
local CC_METRONOME = nil

-- ---------------------------------------------------------------------------

local PLACES = { info = 0, name = 1, line = 2, small = 3 }
local KEEP_ALWAYS, KEEP_MOMENT = 1, 2
local TEXT_MAX = 32
-- Sent again every so often, which the pedal takes without a flicker, so a
-- pedal plugged in or restarted while it runs catches up
local RESEND_SECONDS = 5

-- The characters the display cannot draw, as the tools spell them
-- (python/lib/displayText.py); any other one is "?"
local SPELLED = {
  [0x9]=" ",[0xA0]=" ",[0xA1]="!",[0xA8]=" ",[0xAA]="a",[0xAB]="\"",[0xAF]=" ",[0xB0]="o",[0xB2]="2",
  [0xB3]="3",[0xB4]=" ",[0xB7]=".",[0xB8]=" ",[0xB9]="1",[0xBA]="o",[0xBB]="\"",[0xBC]="1?4",
  [0xBD]="1?2",[0xBE]="3?4",[0xC0]="A",[0xC1]="A",[0xC2]="A",[0xC3]="A",[0xC4]="A",[0xC5]="A",
  [0xC6]="AE",[0xC7]="C",[0xC8]="E",[0xC9]="E",[0xCA]="E",[0xCB]="E",[0xCC]="I",[0xCD]="I",[0xCE]="I",
  [0xCF]="I",[0xD1]="N",[0xD2]="O",[0xD3]="O",[0xD4]="O",[0xD5]="O",[0xD6]="O",[0xD7]="x",[0xD8]="O",
  [0xD9]="U",[0xDA]="U",[0xDB]="U",[0xDC]="U",[0xDD]="Y",[0xDE]="Th",[0xDF]="ss",[0xE0]="a",
  [0xE1]="a",[0xE2]="a",[0xE3]="a",[0xE4]="a",[0xE5]="a",[0xE6]="ae",[0xE7]="c",[0xE8]="e",[0xE9]="e",
  [0xEA]="e",[0xEB]="e",[0xEC]="i",[0xED]="i",[0xEE]="i",[0xEF]="i",[0xF1]="n",[0xF2]="o",[0xF3]="o",
  [0xF4]="o",[0xF5]="o",[0xF6]="o",[0xF7]="/",[0xF8]="o",[0xF9]="u",[0xFA]="u",[0xFB]="u",[0xFC]="u",
  [0xFD]="y",[0xFE]="th",[0xFF]="y",[0x100]="A",[0x101]="a",[0x102]="A",[0x103]="a",[0x104]="A",
  [0x105]="a",[0x106]="C",[0x107]="c",[0x108]="C",[0x109]="c",[0x10A]="C",[0x10B]="c",[0x10C]="C",
  [0x10D]="c",[0x10E]="D",[0x10F]="d",[0x110]="D",[0x111]="d",[0x112]="E",[0x113]="e",[0x114]="E",
  [0x115]="e",[0x116]="E",[0x117]="e",[0x118]="E",[0x119]="e",[0x11A]="E",[0x11B]="e",[0x11C]="G",
  [0x11D]="g",[0x11E]="G",[0x11F]="g",[0x120]="G",[0x121]="g",[0x122]="G",[0x123]="g",[0x124]="H",
  [0x125]="h",[0x128]="I",[0x129]="i",[0x12A]="I",[0x12B]="i",[0x12C]="I",[0x12D]="i",[0x12E]="I",
  [0x12F]="i",[0x130]="I",[0x131]="i",[0x132]="IJ",[0x133]="ij",[0x134]="J",[0x135]="j",[0x136]="K",
  [0x137]="k",[0x139]="L",[0x13A]="l",[0x13B]="L",[0x13C]="l",[0x13D]="L",[0x13E]="l",[0x13F]="L?",
  [0x140]="l?",[0x141]="L",[0x142]="l",[0x143]="N",[0x144]="n",[0x145]="N",[0x146]="n",[0x147]="N",
  [0x148]="n",[0x149]="?n",[0x14C]="O",[0x14D]="o",[0x14E]="O",[0x14F]="o",[0x150]="O",[0x151]="o",
  [0x152]="OE",[0x153]="oe",[0x154]="R",[0x155]="r",[0x156]="R",[0x157]="r",[0x158]="R",[0x159]="r",
  [0x15A]="S",[0x15B]="s",[0x15C]="S",[0x15D]="s",[0x15E]="S",[0x15F]="s",[0x160]="S",[0x161]="s",
  [0x162]="T",[0x163]="t",[0x164]="T",[0x165]="t",[0x168]="U",[0x169]="u",[0x16A]="U",[0x16B]="u",
  [0x16C]="U",[0x16D]="u",[0x16E]="U",[0x16F]="u",[0x170]="U",[0x171]="u",[0x172]="U",[0x173]="u",
  [0x174]="W",[0x175]="w",[0x176]="Y",[0x177]="y",[0x178]="Y",[0x179]="Z",[0x17A]="z",[0x17B]="Z",
  [0x17C]="z",[0x17D]="Z",[0x17E]="z",[0x17F]="s",[0x2013]="-",[0x2014]="-",[0x2018]="'",[0x2019]="'",
  [0x201A]=",",[0x201C]="\"",[0x201D]="\"",[0x201E]="\"",[0x2026]="...",[0x2212]="-",
}

-- The text as the display can draw it: printable ASCII
local function display_text(text)
  local out = {}
  local ok = pcall(function()
    for _, cp in utf8.codes(text) do
      if cp >= 0x20 and cp <= 0x7E then
        out[#out + 1] = string.char(cp)
      elseif (cp >= 0x300 and cp <= 0x36F) then
        -- a mark that did not join its letter
      else
        out[#out + 1] = SPELLED[cp] or "?"
      end
    end
  end)
  if not ok then
    -- Not UTF-8: one byte per character
    out = {}
    for i = 1, #text do
      local b = text:byte(i)
      out[#out + 1] = (b >= 0x20 and b <= 0x7E) and string.char(b) or "?"
    end
  end
  return table.concat(out)
end

-- F0 7D 48 place keep text F7: text on the display
local function text_sysex(text, place, keep)
  return string.char(0xF0, 0x7D, 0x48, PLACES[place], keep)
    .. display_text(text):sub(1, TEXT_MAX) .. string.char(0xF7)
end

local function find_output()
  for i = 0, reaper.GetNumMIDIOutputs() - 1 do
    local ok, name = reaper.GetMIDIOutputName(i, "")
    if ok and name:find(DEVICE, 1, true) then
      return i
    end
  end
  return nil
end

local function send(output, msg)
  if output then
    reaper.SendMIDIMessageToHardware(output, msg)
  end
end

-- The region and the last marker at a time, by name; nil for none
local function names_at(time)
  local marker, region = reaper.GetLastMarkerAndCurRegion(0, time)
  local song, part
  if region >= 0 then
    local _, _, _, _, name = reaper.EnumProjectMarkers3(0, region)
    song = name
  end
  if marker >= 0 then
    local _, _, _, _, name = reaper.EnumProjectMarkers3(0, marker)
    part = name
  end
  return song, part, marker
end

local function project_song()
  if not PROJECT_NAME_AS_SONG then
    return ""
  end
  local name = reaper.GetProjectName(0)
  return (name:gsub("%.[Rr][Pp][Pp]$", ""))
end

local TRANSPORT = {
  { cc = CC_PLAY, on = function(state) return state & 1 == 1 end },
  { cc = CC_RECORD, on = function(state) return state & 4 == 4 end },
  { cc = CC_REPEAT, on = function() return reaper.GetToggleCommandState(1068) == 1 end },
  { cc = CC_METRONOME, on = function() return reaper.GetToggleCommandState(40364) == 1 end },
}

-- What has gone out, to send only what changed
local sent = { output = nil, song = nil, marker = nil, cc = {}, at = -math.huge }

-- One look at the project, sending what changed since the last
local function step()
  local now = reaper.time_precise()
  local again = now - sent.at >= RESEND_SECONDS
  if again then
    sent.output, sent.at, sent.cc = find_output(), now, {}
  end
  local output = sent.output

  local state = reaper.GetPlayState()
  local playing = state & 1 == 1 or state & 4 == 4
  local time = playing and reaper.GetPlayPosition() or reaper.GetCursorPosition()
  local song, part, marker = names_at(time)
  song = song or project_song()

  if song ~= sent.song or again then
    send(output, text_sysex(song, SONG_PLACE, KEEP_ALWAYS))
    sent.song = song
  end
  if marker ~= sent.marker then
    -- Only a marker reached by playing; one found where the cursor was put
    -- is where the song already is
    if PART_PLACE and playing and part and part ~= "" and sent.marker ~= nil then
      send(output, text_sysex(part, PART_PLACE, KEEP_MOMENT))
    end
    sent.marker = marker
  end

  for _, t in ipairs(TRANSPORT) do
    if t.cc then
      local value = t.on(state) and 127 or 0
      if sent.cc[t.cc] ~= value then
        send(output, string.char(0xB0 + CC_CHANNEL - 1, t.cc, value))
        sent.cc[t.cc] = value
      end
    end
  end
  return output
end

-- Back to what the bank shows
local function stop()
  local output = find_output()
  send(output, text_sysex("", SONG_PLACE, KEEP_ALWAYS))
end

if MCC_TEST then
  return { display_text = display_text, text_sysex = text_sysex, step = step, stop = stop, sent = sent }
end

if not reaper.SendMIDIMessageToHardware then
  reaper.ShowMessageBox("This REAPER is too old for this script: it cannot send MIDI to a device.", "MIDI Commander", 0)
  return
end
if not find_output() then
  reaper.ShowMessageBox("No MIDI output named \"" .. DEVICE .. "\" is enabled.\n\n"
    .. "Tick the pedal's output as Enabled in Preferences > Audio > MIDI Inputs/Outputs, "
    .. "and run the script again.", "MIDI Commander", 0)
  return
end

local _, _, section, command = reaper.get_action_context()
reaper.SetToggleCommandState(section, command, 1)
reaper.RefreshToolbar2(section, command)

local function loop()
  step()
  reaper.defer(loop)
end

reaper.atexit(function()
  stop()
  reaper.SetToggleCommandState(section, command, 0)
  reaper.RefreshToolbar2(section, command)
end)
loop()
