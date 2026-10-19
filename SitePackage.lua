--------------------------------------------------------------------------
-- The SitePackage customization for UGent-HPC & VUB-HPC
-- Ward Poelmans <ward.poelmans@ugent.be>
-- Kenneth Hoste <kenneth.hoste@ugent.be>
-- Ward Poelmans <ward.poelmans@vub.be>
--------------------------------------------------------------------------

require("strict")
require("cmdfuncs")
require("utils")
require("parseVersion")
local syslog = require("posix.syslog")
local Dbg   = require("Dbg")
local dbg   = Dbg:dbg()
local hook  = require("Hook")
local FrameStk  = require("FrameStk")
local MT    = require("MT")
local cluster = os.getenv("VSC_INSTITUTE_CLUSTER") or ""
local email
if cluster == "sofia" then
    email = "support@vscentrum.be"
else
    email = "hpc@vub.be"
end


local function logmsg(logTbl)
    -- Print to syslog with generic header
    -- All the elements in the table logTbl are
    -- added in order. Expect format:
    -- logTbl[#logTbl+1] = {'log_key', 'log_value'}

    local jobid = os.getenv("SLURM_JOB_ID") or ""
    local user = os.getenv("USER")
    local arch = os.getenv("VSC_ARCH_LOCAL") or ""

    local msg = string.format("username=%s, cluster=%s, arch=%s, jobid=%s",
                              user, cluster, arch, jobid)

    for _, val in ipairs(logTbl) do
        msg = msg .. string.format(", %s=%s", val[1], val[2] or "")
    end

    -- Don't log any modules loaded by the monitoring
    if user ~= "zabbix" then
        syslog.openlog("lmod")
        syslog.syslog(syslog.LOG_NOTICE, msg)
        syslog.closelog()
    end
end


-- Cache module age per generation
-- The visible hook evaluates each module many times per `ml av`, but the age
-- only depends on the toolchain generation in the path.
-- os.time() can be expensive as it makes glibc re-stat /etc/localtime on every
-- call when TZ is unset
local s_moduleAgeT = {}

local function module_age(modT)
    -- Calculate the age of a module, relative to the current toolchain generation
    -- modT should have a entry 'fn' with the module path
    -- returns the age in 6-month toolchain generations, or nil when the
    -- toolchain version cannot be determined from the module path

    local tcyear, tcsuffix = modT.fn:match("^/apps/brussel/.*/modules/(20[0-9][0-9])([^/]+)/all/")
    if tcyear == nil or tcsuffix == nil then return nil end

    -- old style toolchains: {year}[ab]
    -- a = January, b = July
    local suffixmonth = {a=1, b=7}
    local tcmonth = suffixmonth[tcsuffix]
    -- new style toolchains: {year}.%d
    -- 1 = January, 2 = May, 3 = September
    if tcmonth == nil then
        local quarter = tonumber(tcsuffix:match("^%.(%d+)$"))
        tcmonth = quarter and (quarter - 1) * 4 + 1
    end
    -- anything else is rejected
    if tcmonth == nil or tcmonth < 1 or tcmonth > 12 then return nil end

    local key = tcyear .. tcsuffix
    local age = s_moduleAgeT[key]
    if age == nil then
        local tcstamp = os.time({year=tcyear, month=tcmonth, day=1})

        -- 1 month is 2629743 seconds
        age = math.floor((os.time() - tcstamp) / (6 * 2629743))
        s_moduleAgeT[key] = age
    end
    return age
end


local function load_hook(t)
    -- Called every time a module is loaded
    -- the arg t is a table:
    --     t.modFullName:  the module full name: (i.e: gcc/4.7.2)
    --     t.fn:           the file name: (i.e /apps/modulefiles/Core/gcc/4.7.2.lua)

    -- unclear whether this is needed (and rtmclay agrees), but no harm in keeping it
    if (mode() ~= "load") then return end

    -- if userload is yes, the user request to load this module. Else
    -- it is getting loaded as a dependency.
    local frameStk = FrameStk:singleton()
    -- yes means that it is a module directly request by the user
    local userload = (frameStk:atTop()) and "yes" or "no"

    local logTbl      = {}
    logTbl[#logTbl+1] = {"userload", userload}
    logTbl[#logTbl+1] = {"module", t.modFullName}
    logTbl[#logTbl+1] = {"fn", t.fn}

    logmsg(logTbl)

    if cluster ~= "sofia" then
        -- inform/warn users about old modules (only directly loaded ones)
        local age = module_age(t)
        if age and frameStk:atTop() then
            if age > 8 then
                -- warning for 4 years old
                LmodWarning{msg="vub_very_old_module", fullName=t.modFullName}
            elseif age > 6 then
                -- inform for 3 years old
                LmodMessage{msg="vub_old_module", fullName=t.modFullName}
            end
        end
    end
end

--[[
local function restore_hook(t)
    -- This hook is called after a restore operation
    -- the arg t is a table:
    --     t.collection: the input name of the collection
    --     t.name:       the output name of the collection
    --     t.fn:         The file name: (i.e /apps/modulefiles/Core/gcc/4.7.2.lua)

    dbg.start{"restore_hook"}

    local def_cluster = os.getenv("VSC_DEFAULT_CLUSTER_MODULE")
    if (not cluster or not def_cluster) then return end

    if (cluster == def_cluster) then return end

    dbg.print{"Have: ", cluster, " Switch to ", def_cluster}

    Swap("cluster/" .. cluster, "cluster/" .. def_cluster)

    dbg.fini()
end
]]--

local function startup_hook(usrCmd)
    -- This hook is called right after starting Lmod
    -- usrCmd holds the currect active command
    -- if you want access to all give arguments, use
    -- masterTbl
    dbg.start{"startup_hook"}

    -- masterTbl has all info about the arguments passed to Lmod
    local masterTbl = masterTbl()

    dbg.print{"Received usrCmd: ", usrCmd, "\n"}
    dbg.print{"masterTbl:", masterTbl, "\n"}

    -- Log how Lmod was called
    local fullargs    = table.concat(masterTbl.pargs, " ") or ""
    local logTbl      = {}
    logTbl[#logTbl+1] = {"cmd", usrCmd}
    logTbl[#logTbl+1] = {"args", fullargs}

    logmsg(logTbl)

    dbg.fini()
end

local function msg_hook(mode, output)
    -- mode is avail, list and spider
    -- output is a table with the current output

    dbg.start{"msg_hook"}

    dbg.print{"Mode is ", mode, "\n"}

    if mode == "avail" then
        output[#output+1] = ("\nIf you need help with software that is not listed, please contact %s\n"):format(email)
    end

    dbg.fini()

    return output
end

-- This gets called on every message, warning and error
local function errwarnmsg_hook(kind, key, msg, t)
    -- kind is either lmoderror, lmodwarning or lmodmessage
    -- key is a unique key for the message (see messageT.lua)
    -- msg is the actual message to display (as string)
    -- t is a table with the keys used in msg
    dbg.start{"errwarnmsg_hook"}

--    dbg.print{"kind: ", kind," key: ",key,"\n"}
--    dbg.print{"keys: ", t}

    if key == "e_No_AutoSwap" then
        -- Customize this error for EasyBuild modules
        -- When the users gets this error, it mostly likely means
        -- that they are trying to load modules belonging to different version of the same toolchain
        --
        -- find the module name causing the issue (almost always toolchain module)
        local sname = t.sn
        local frameStk = FrameStk:singleton()

        local errmsg = {"A different version of the '" .. sname .. "' module is already loaded (see output of 'ml')."}
        if not frameStk:empty() then
            local framesn = frameStk:sn()
            errmsg[#errmsg+1] = "You should load another '" .. framesn .. "' module that is compatible with " ..
                                "the currently loaded version of '" .. sname .. "'."
            errmsg[#errmsg+1] = "Use 'ml spider " .. framesn .. "' to get an overview of the available versions."
        end
        errmsg[#errmsg+1] = "\n"

        msg = table.concat(errmsg, "\n")
    end

    if kind == "lmoderror" or kind == "lmodwarning" then
        msg = msg .. ("\nIf you don't understand the warning or error, please contact %s"):format(email)
    end

    -- log any errors users get
    if kind == "lmoderror" then
        local logTbl      = {}
        logTbl[#logTbl+1] = {"error", key}

        for tkey, tval in pairs(t) do
            if tkey == 'message' then
                tval = tval
            end
            logTbl[#logTbl+1] = {tkey, tval}
        end

        logmsg(logTbl)
    end

    dbg.fini()

    return msg
end


local function site_name_hook()
    -- set the SiteName, it must be a valid
    -- shell variable name.
    return "VUB_HPC"
end


-- To combine EasyBuild with XALT
local function packagebasename(t)
    -- Use the EBROOT variables in the module
    -- as base dir for the reverse map
    t.patDir = "^EBROOT.*"
end


local function visible_hook(modT)
    -- modT is a table with: fullName, sn, fn and isVisible
    -- The latter is a boolean to determine if a module is visible or not

    local mt = MT:singleton()

    if modT.fullName:find("cluster/%.") then
        modT.isVisible = false
    elseif modT.fullName:find("EESSI/") then
        modT.isVisible = false
    elseif modT.fullName:find("JupyterHub/") then
        modT.isVisible = false
    elseif cluster ~= "sofia" then
        if modT.fn:find("^/apps/brussel/CO7/") then
            if not mt:exists('legacy-software') then
                modT.isVisible = false
                return
            end
        else
            local age = module_age(modT)
            if age and age > 6 then
                modT.isVisible = false
            end
        end
    end
end


-- The spider that `avail` uses executes every modulefile and follows the
-- paths they add via `module use` (dynamic spidering).  legacy-software
-- adds the CO7 tree (~1100 modulefiles).
--
-- Solve with spider hook that strips the legacy cluster paths from the
-- spider's pending directory stack so they are never walked.  This does not
-- affect users who actually load the legacy software, as real loads do not go
-- through the spider, and once it is loaded the module sets $VUB_LEGACY_SOFTWARE
-- activating the escape hatch.
local LEGACY_PREFIXES = {
    "/apps/brussel/CO7/",
    -- "/apps/brussel/RL8/",  -- not yet used in a legacy-software module
}

local function is_legacy_path(p)
    if type(p) ~= "string" then return false end
    for i = 1, #LEGACY_PREFIXES do
        local pre = LEGACY_PREFIXES[i]
        if p:sub(1, #pre) == pre then
            return true
        end
    end
    return false
end

local function load_spider_hook()
    if os.getenv("VUB_LEGACY_SOFTWARE") == "1" then
        return
    end
    local oT = optionTbl()
    local dirStk = oT.dirStk
    if type(dirStk) == "table" then
        -- Spider:findAllModules holds a local reference to this exact
        -- array, so mutate it in place instead of reassigning.
        local w = 1
        for i = 1, #dirStk do
            local p = dirStk[i]
            if not is_legacy_path(p) then
                dirStk[w] = p
                w = w + 1
            end
        end
        for i = w, #dirStk do
            dirStk[i] = nil
        end
    end
    local mmT = oT.mpathMapT
    if type(mmT) == "table" then
        for k in pairs(mmT) do
            if is_legacy_path(k) then
                mmT[k] = nil
            end
        end
    end
end


local native_userInGroup = userInGroup

local function userInGroupFallback(group)
    -- Apptainer doesn't inherit supplementary groups, but it injects them
    -- into /etc/group (e.g. "babaqus:x:2610114:vsc12345"), so fall back
    -- to parsing that.
    dbg.start{"userInGroupFallback"}
    dbg.print{"group: ", group, "\n"}

    if native_userInGroup(group) then
        dbg.fini()
        return true
    end

    local user = os.getenv("USER") or ""
    if user == "" then
        dbg.fini()
        return false
    end

    local f = io.open("/etc/group", "r")
    if not f then
        dbg.fini()
        return false
    end

    local in_group = false
    for line in f:lines() do
        local name, members = line:match("^([^:]*):[^:]*:[^:]*:(.*)$")
        if name == group then
            for member in members:gmatch("[^,]+") do
                if member == user then
                    in_group = true
                    break
                end
            end
            break
        end
    end
    f:close()

    dbg.print{"in_group: ", in_group, "\n"}
    dbg.fini()

    return in_group
end


local function get_avail_memory()
    -- If a limit is set, return the maximum allowed memory, else nil

    -- look for the memory cgroup (if any):
    -- for cgroupv2: find the hierarchegy and the memory controller
    -- for cgroupv1: look for the memory controller
    local lines = {}
    for line in io.lines("/proc/self/cgroup") do
        table.insert(lines, line)
    end

    local cgroup = nil
    local memory_filepath
    -- if it's one line: cgroupv2
    if #lines == 1 then
        cgroup = lines[1]:match("^[0-9]+::(.*)$")
        memory_filepath = "/sys/fs/cgroup/_CGROUP_SET_/memory.max"

    else
        for _, line in ipairs(lines) do
            cgroup = line:match("^[0-9]+:memory:(.*)$")
            if cgroup then
                break
            end
        end
        memory_filepath = "/sys/fs/cgroup/memory/_CGROUP_SET_/memory.memsw.limit_in_bytes"
    end

    if not cgroup then
        return nil
    end

    -- Slurm tasks are only limited by the job step that launched it
    cgroup = cgroup:gsub("/task_[%d]+$", "")

    -- read the current maximum allowed memory usage (memory)
    memory_filepath = memory_filepath:gsub("_CGROUP_SET_", cgroup)
    local memory_file = io.open(memory_filepath)
    if not memory_file then
        return nil
    end
    local memory_value = tonumber(memory_file:read())
    memory_file:close()

    -- if the value is 2^63-1 (rounded down to multiples of 4096), it's unlimited
    if memory_value == 9223372036854771712 then
        return nil
    end

    return memory_value
end


hook.register("load", load_hook)
hook.register("load_spider", load_spider_hook)
-- Needs more testing before enabling:
-- hook.register("restore", restore_hook)
hook.register("startup", startup_hook)
hook.register("msgHook", msg_hook)
hook.register("SiteName", site_name_hook)
hook.register("packagebasename", packagebasename)
hook.register("errWarnMsgHook", errwarnmsg_hook)
hook.register("isVisibleHook", visible_hook)

sandbox_registration{
    get_avail_memory = get_avail_memory,
}
if os.getenv("APPTAINER_CONTAINER") then
    sandbox_registration{
        userInGroup = userInGroupFallback,
    }
end
