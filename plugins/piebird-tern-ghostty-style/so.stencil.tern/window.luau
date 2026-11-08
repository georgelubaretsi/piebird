-- piebird-tern-ghostty-style: the look is the style sheets in plugin.toml's styles. This window half
-- holds one switch: omp's thoughts left open, as in Ghostty (the default), or foldable as Tern
-- folds them. Open installs thoughts-open.css as a sheet; foldable empties that sheet, so Tern's
-- own fold works: the chevron shows and a click on the head folds and unfolds a thought.
--
-- The mode lives in tern.kv, which every window shares. The command flips what this window shows
-- and saves it; another window takes it up the next time a pane in it gets focus, or when it
-- starts. Phones and the web tab get the style sheets from their host but run no window half here:
-- phone.css keeps thoughts open on phones, and the web tab in a desktop browser folds them as Tern does.

local KEY = "thoughts"
local OPEN = "open"
local FOLDABLE = "foldable"
local CHORD = "cmd+alt+t"
local SHEET_MAX_BYTES = 64 * 1024

local function read_sheet(): string
	local ok, text = pcall(tern.fs.read, tern.plugin.dir .. "/thoughts-open.css", SHEET_MAX_BYTES)
	if ok then
		return text
	end
	tern.log.error("piebird-tern-ghostty-style: thoughts-open.css unreadable, thoughts fold: " .. tostring(text))
	return ""
end

local SHEET = read_sheet()

-- The saved mode; anything but "foldable" (nothing saved, a store that can't be read) is open.
local function saved(): string
	local ok, value = pcall(tern.kv.get, KEY)
	if ok and value == FOLDABLE then
		return FOLDABLE
	end
	return OPEN
end

local shown = OPEN
local show: (mode: string) -> ()

local function register()
	tern.command({
		id = "thoughts",
		title = if shown == OPEN then "Fold thoughts" else "Keep thoughts open",
		icon = "brain",
		keys = { CHORD },
		run = function(cx)
			local mode = if shown == OPEN then FOLDABLE else OPEN
			tern.kv.set(KEY, mode) -- raises when it can't save: the command fails and nothing changes
			show(mode)
			cx:toast("info", if mode == OPEN then "Thoughts stay open" else "Thoughts fold")
		end,
	})
end

-- Installs the sheet for `mode` and names the command after the other one.
function show(mode: string)
	shown = mode
	tern.css("thoughts", if mode == OPEN then SHEET else "")
	register()
end

show(saved())

-- Another window flipped the mode: follow it here too.
tern.on("focus", function()
	local mode = saved()
	if mode ~= shown then
		show(mode)
	end
end)
