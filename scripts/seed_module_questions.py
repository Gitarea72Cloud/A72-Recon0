#!/usr/bin/env python3
"""Seed the 11 module assessments (MODULE_META + starter question banks).

For each module (module-01..module-11, matching the programme calendar
in Calendario_Academico.pdf):
  - one MODULE_META item (PK="MODULE_META", SK=<moduleId>) with the
    module's title/order/dateRange, unlocked=False initially -- the
    instructor turns each one on from the admin panel's Modules tab as
    that module's classes finish.
  - 5 starter free-text questions (type: free-text, checkpoint=domain=
    moduleId), 3 progressive hints each, same conceptual-question
    convention as the placement test's red_team/blue_team/grey_team
    items in seed_questions.py -- no terminal/scenario exercises in
    this first pass. Written from each module's actual calendar
    description; the instructor can add/edit more anytime via the
    admin Questions tab (including AI-assisted drafting once Bedrock
    access is approved -- that path is already domain-agnostic for
    free-text questions).

Usage:
    python3 scripts/seed_module_questions.py --table a72-recon0-dev --region eu-south-2
"""
import argparse
import boto3


def module_meta(module_id, order, title, date_range):
    return {
        "PK": "MODULE_META", "SK": module_id,
        "title": title, "order": order, "dateRange": date_range,
        "domain": module_id, "unlocked": False,
    }


def q(module_id, n, prompt, answer_key, hints):
    return {
        "PK": f"QUESTION#{module_id}", "SK": f"ITEM#{module_id}-{n:03d}",
        "checkpoint": module_id, "type": "free-text",
        "prompt": prompt, "answer_key": answer_key, "hints": hints,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--region", default="eu-south-2")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(args.table)

    modules = [
        module_meta("module-01", 1, "Fundamentos: Linux, Windows y Networking", "19-29 Oct 2026"),
        module_meta("module-02", 2, "OSINT y Análisis Forense de Redes", "3-20 Nov 2026"),
        module_meta("module-03", 3, "Explotación de Servicios y Máquinas Vulnerables", "11 Nov - 17 Dic 2026"),
        module_meta("module-04", 4, "Aplicaciones Web y OWASP Top 10", "12 Ene - 18 Feb 2027"),
        module_meta("module-05", 5, "Hack The Box: Máquinas Reales", "22 Feb - 4 Mar 2027"),
        module_meta("module-06", 6, "Active Directory: Ataques y Persistencia", "8 Mar - 13 Abr 2027"),
        module_meta("module-07", 7, "Blue Team: Defensa, SIEM y Respuesta a Incidentes", "Nov 2026 - Abr 2027"),
        module_meta("module-08", 8, "Escalada de Privilegios: Linux y Windows", "22 Abr - 11 May 2027"),
        module_meta("module-09", 9, "Pivoting y Movimiento Lateral en Redes", "12-21 May 2027"),
        module_meta("module-10", 10, "Seguridad en IA Generativa (GenAI)", "24 May - 9 Jun 2027"),
        module_meta("module-11", 11, "Repaso Final y Consolidación", "10-17 Jun 2027"),
    ]

    # ------------------------------------------------------------------
    # Module 1 -- Fundamentos: Linux, Windows y Networking
    # ------------------------------------------------------------------
    module_01_items = [
        q("module-01", 1,
          "In Linux, what's the name of the file that stores information about "
          "system user accounts -- username, UID, home directory, and default shell?",
          ["/etc/passwd", "etc/passwd", "passwd"],
          ["It lives under /etc, alongside most other system configuration files.",
           "Its name is also the name of the classic command used to change a password.",
           "The answer is /etc/passwd."]),
        q("module-01", 2,
          "What Linux command changes a file or directory's permissions, e.g. to 755?",
          "chmod",
          ["It's short for \"change mode\".",
           "You'd run it before ls -l to confirm the new permission bits.",
           "The answer is chmod."]),
        q("module-01", 3,
          "In networking, what do we call the device that connects multiple networks "
          "together and forwards traffic between them based on IP address?",
          "router",
          ["It operates at Layer 3 of the OSI model, unlike a switch (Layer 2).",
           "Your home internet box that connects your LAN to your ISP is one of these.",
           "The answer is router."]),
        q("module-01", 4,
          "In Bash scripting, what do we call the special first line of a script "
          "(e.g. #!/bin/bash) that tells the system which interpreter should run it?",
          ["shebang", "hashbang", "she-bang"],
          ["It's named after the two characters it starts with: # and !.",
           "Without it, the system doesn't know whether to hand the script to bash, python, etc.",
           "The answer is shebang."]),
        q("module-01", 5,
          "What's the term for creating and running virtual machines on a single "
          "physical host, letting you isolate multiple operating systems or environments?",
          "virtualization",
          ["It's what makes lab platforms like VirtualBox or VMware possible.",
           "The word describes making something behave as if it were real hardware, "
           "when it isn't.",
           "The answer is virtualization."]),
    ]

    # ------------------------------------------------------------------
    # Module 2 -- OSINT y Análisis Forense de Redes
    # ------------------------------------------------------------------
    module_02_items = [
        q("module-02", 1,
          "What does the acronym OSINT stand for -- the practice of gathering "
          "information about a target using only publicly available sources?",
          ["open source intelligence", "open-source intelligence"],
          ["The first word describes where the information comes from -- nothing hacked or private.",
           "The second word is the same one used in \"business intelligence\".",
           "The answer is open source intelligence (OSINT)."]),
        q("module-02", 2,
          "What free, widely-used tool lets you capture and inspect network traffic "
          "packet by packet, applying filters to isolate protocols or conversations?",
          "wireshark",
          ["Its logo is a shark, which is a hint about its name.",
           "It's the de-facto standard GUI tool for packet analysis.",
           "The answer is Wireshark."]),
        q("module-02", 3,
          "When analyzing a suspicious email, what part of the message would you "
          "inspect to trace the path it took across mail servers before reaching you?",
          ["received headers", "email headers", "received header"],
          ["It's not the visible body of the email -- it's metadata attached to it.",
           "Most email clients let you view this as \"show original\" or \"view source\".",
           "The answer is the (received) email headers."]),
        q("module-02", 4,
          "What's the general term for manipulating people into revealing confidential "
          "information or taking an action that compromises security, rather than "
          "exploiting a technical flaw?",
          "social engineering",
          ["It targets human trust and psychology, not code or systems directly.",
           "Phishing is one specific example of this broader category.",
           "The answer is social engineering."]),
        q("module-02", 5,
          "Which Wi-Fi security protocol -- the newest of WEP, WPA, WPA2, WPA3 -- offers "
          "the strongest protection for a home or corporate wireless network?",
          "wpa3",
          ["It's the most recently released of the four.",
           "Its number is one higher than the widely-deployed WPA2.",
           "The answer is WPA3."]),
    ]

    # ------------------------------------------------------------------
    # Module 3 -- Explotación de Servicios y Máquinas Vulnerables
    # ------------------------------------------------------------------
    module_03_items = [
        q("module-03", 1,
          "What's the term for the early-stage process of systematically probing a "
          "target to identify open ports, running services, and their versions?",
          ["enumeration", "service enumeration"],
          ["It comes right after basic port scanning, digging deeper into what's found.",
           "The goal is building a detailed list -- to \"enumerate\" -- of what's exposed.",
           "The answer is enumeration."]),
        q("module-03", 2,
          "What command-line tool lets you search a local database of known exploits "
          "(from Exploit-DB) by keyword, such as a service name and version?",
          "searchsploit",
          ["Its name is a straightforward mash-up of what it does.",
           "It ships with a local, offline copy of the Exploit-DB archive.",
           "The answer is searchsploit."]),
        q("module-03", 3,
          "What popular tool acts as an intercepting proxy, letting you capture, "
          "inspect, and modify HTTP/HTTPS traffic between your browser and a web app?",
          ["burp suite", "burpsuite", "burp"],
          ["Its name references a rude noise, which is memorable but not very professional.",
           "It's the industry-standard tool for manual web application testing.",
           "The answer is Burp Suite."]),
        q("module-03", 4,
          "What network scanning tool is most commonly used to discover open ports "
          "and identify service versions on a target host?",
          "nmap",
          ["Its name is short for \"Network Mapper\".",
           "The -sV flag on this tool specifically probes for service versions.",
           "The answer is nmap."]),
        q("module-03", 5,
          "What's the general term for taking advantage of a known weakness in a "
          "system or service to gain unauthorized access or unintended behavior?",
          ["exploitation", "exploit"],
          ["It's the phase that follows enumeration once a weakness has been found.",
           "The tool or code used to do this is itself called by the same name.",
           "The answer is exploitation (an exploit)."]),
    ]

    # ------------------------------------------------------------------
    # Module 4 -- Aplicaciones Web y OWASP Top 10
    # ------------------------------------------------------------------
    module_04_items = [
        q("module-04", 1,
          "What's the general term for sending large volumes of crafted or randomized "
          "input at an application to discover hidden endpoints, parameters, or "
          "unexpected crashes?",
          "fuzzing",
          ["Tools like ffuf or wfuzz are named directly after this technique.",
           "The input is often nonsensical or malformed on purpose, to provoke odd behavior.",
           "The answer is fuzzing."]),
        q("module-04", 2,
          "What's the name of the vulnerability where an attacker injects malicious "
          "SQL statements into an application's database query?",
          ["sql injection", "sqli"],
          ["It happens when user input is concatenated straight into a database query.",
           "SQLMap is a well-known tool built specifically to automate finding and exploiting this.",
           "The answer is SQL injection (SQLi)."]),
        q("module-04", 3,
          "What's the vulnerability called where an attacker manipulates a file-path "
          "parameter (e.g. using ../../) to access files outside the intended directory?",
          ["path traversal", "directory traversal"],
          ["The classic payload pattern uses repeated \"../\" sequences.",
           "It lets an attacker \"traverse\" up and out of the folder the app meant to restrict them to.",
           "The answer is path traversal (directory traversal)."]),
        q("module-04", 4,
          "What's the name of the vulnerability where an attacker injects malicious "
          "JavaScript into a web page that then runs in other users' browsers?",
          ["cross-site scripting", "xss"],
          ["Its abbreviation starts with X specifically to avoid confusion with CSS (stylesheets).",
           "Reflected, stored, and DOM-based are the three common variants.",
           "The answer is cross-site scripting (XSS)."]),
        q("module-04", 5,
          "What's the vulnerability called where an attacker tricks a server into "
          "making requests to internal or unintended destinations on its behalf?",
          ["server-side request forgery", "ssrf"],
          ["The server itself is the one that ends up making the malicious request, not the attacker directly.",
           "It's often used to reach internal-only services or cloud metadata endpoints.",
           "The answer is server-side request forgery (SSRF)."]),
    ]

    # ------------------------------------------------------------------
    # Module 5 -- Hack The Box: Máquinas Reales
    # ------------------------------------------------------------------
    module_05_items = [
        q("module-05", 1,
          "On Hack The Box and similar platforms, what's the term for the "
          "user-level flag file you retrieve to prove initial access to a machine?",
          ["user flag", "user.txt"],
          ["It's distinct from the higher-privilege flag you get after escalating.",
           "It's typically named literally with \"user\" in the filename.",
           "The answer is the user flag (user.txt)."]),
        q("module-05", 2,
          "What's the standard first phase of any pentesting methodology, before "
          "any exploitation, where you identify live hosts, open ports, and services?",
          ["reconnaissance", "recon", "enumeration"],
          ["It's often shortened to a five-letter word in casual conversation.",
           "\"Know your target before you touch it\" describes this phase.",
           "The answer is reconnaissance (recon)."]),
        q("module-05", 3,
          "After gaining a low-privilege shell on a target, what's the general term "
          "for the process of increasing your access to administrator/root level?",
          ["privilege escalation", "privesc"],
          ["It's often abbreviated to a five-letter shorthand ending in \"esc\".",
           "SUID binaries and misconfigured services are common ways to achieve this on Linux.",
           "The answer is privilege escalation (privesc)."]),
        q("module-05", 4,
          "What's the term for a shell where the compromised machine connects back "
          "out to the attacker's listener, useful when the target is behind a firewall?",
          "reverse shell",
          ["It's the opposite direction of a \"bind shell\", where the target listens instead.",
           "Outbound connections are often allowed even when inbound ones are blocked -- that's why this works.",
           "The answer is a reverse shell."]),
        q("module-05", 5,
          "What lightweight utility is commonly used to set up a simple listener to "
          "catch an incoming reverse shell connection on a given port?",
          ["netcat", "nc"],
          ["It's nicknamed the \"Swiss army knife\" of networking tools.",
           "Its command is just two letters long.",
           "The answer is netcat (nc)."]),
    ]

    # ------------------------------------------------------------------
    # Module 6 -- Active Directory: Ataques y Persistencia
    # ------------------------------------------------------------------
    module_06_items = [
        q("module-06", 1,
          "What free tool visualizes Active Directory relationships, permissions, "
          "and trust paths as a graph, helping identify realistic attack paths to "
          "Domain Admin?",
          "bloodhound",
          ["Its name and logo both reference a dog known for tracking scent trails.",
           "It ingests data collected by a companion tool called SharpHound.",
           "The answer is BloodHound."]),
        q("module-06", 2,
          "What's the name of the attack where an attacker requests a Kerberos "
          "service ticket (TGS) for an account with an SPN set, then cracks it "
          "offline to recover the account's password?",
          ["kerberoasting", "kerberoast"],
          ["It targets service accounts that have a Service Principal Name (SPN) configured.",
           "The ticket involved is a TGS -- a service ticket, not the initial TGT.",
           "The answer is Kerberoasting."]),
        q("module-06", 3,
          "What technique lets an attacker authenticate to other systems using a "
          "captured NTLM password hash directly, without ever knowing the plaintext password?",
          ["pass the hash", "pass-the-hash", "pth"],
          ["Its name describes exactly what's being passed instead of a password.",
           "It's commonly abbreviated to three letters.",
           "The answer is Pass-the-Hash (PtH)."]),
        q("module-06", 4,
          "What's the name of the technique where an attacker extracts password "
          "hashes from a Domain Controller by abusing the directory-replication "
          "protocol, impersonating another DC?",
          "dcsync",
          ["Its name references the legitimate replication process it abuses -- domain controllers syncing with each other.",
           "It's a single word combining \"DC\" and a verb meaning to keep data consistent.",
           "The answer is DCSync."]),
        q("module-06", 5,
          "What's the forged Kerberos ticket called that, once created using the "
          "domain's krbtgt account hash, grants an attacker persistent, near-unlimited "
          "access to the whole domain?",
          "golden ticket",
          ["Its name suggests something extremely valuable and hard to obtain -- like in a certain chocolate-factory story.",
           "It's built from the krbtgt account, the account that signs every Kerberos ticket in the domain.",
           "The answer is a Golden Ticket."]),
    ]

    # ------------------------------------------------------------------
    # Module 7 -- Blue Team: Defensa, SIEM y Respuesta a Incidentes
    # ------------------------------------------------------------------
    module_07_items = [
        q("module-07", 1,
          "What does the acronym SIEM stand for -- the class of system that "
          "centrally collects, normalizes, and correlates security logs to detect threats?",
          ["security information and event management"],
          ["It combines two older categories of tools -- one for managing security info, one for managing events -- into one acronym.",
           "The acronym is pronounced like the name \"Sim\".",
           "The answer is Security Information and Event Management (SIEM)."]),
        q("module-07", 2,
          "What's the structured, step-by-step document called that a security team "
          "follows when responding to a specific type of security incident?",
          ["playbook", "ir playbook", "incident response playbook"],
          ["Sports teams use a document with the same name to plan their strategies.",
           "It's usually written in advance, before the incident it covers ever happens.",
           "The answer is a playbook (IR playbook)."]),
        q("module-07", 3,
          "What well-known public framework catalogs real-world adversary tactics and "
          "techniques, widely used to structure threat hunting and detection engineering?",
          ["mitre att&ck", "att&ck", "mitre attack"],
          ["It's maintained by a well-known US non-profit research organization whose name starts with the same word.",
           "Its name is also an aggressive verb, stylized with an ampersand in the middle.",
           "The answer is MITRE ATT&CK."]),
        q("module-07", 4,
          "What's the proactive security practice called where analysts actively "
          "search a network for signs of compromise, rather than waiting for an "
          "automated alert?",
          "threat hunting",
          ["It's an active, human-driven search rather than a passive, automated one.",
           "The name describes going out looking for something, the way you'd hunt for game.",
           "The answer is threat hunting."]),
        q("module-07", 5,
          "What's the general term for tightening a system's configuration -- "
          "disabling unnecessary services, applying least privilege, patching -- to "
          "reduce its attack surface?",
          "hardening",
          ["It describes making something tougher and more resistant to attack.",
           "You'd \"harden\" a server the same way you might toughen up any weak point.",
           "The answer is hardening."]),
    ]

    # ------------------------------------------------------------------
    # Module 8 -- Escalada de Privilegios: Linux y Windows
    # ------------------------------------------------------------------
    module_08_items = [
        q("module-08", 1,
          "In Linux, what special permission bit, when set on an executable, lets "
          "it run with the file owner's privileges rather than the user who launched "
          "it -- a common privilege-escalation vector when misconfigured?",
          ["suid", "setuid"],
          ["Its name stands for \"Set owner User ID\".",
           "You'd look for this bit using `find / -perm -4000` during enumeration.",
           "The answer is SUID (setuid)."]),
        q("module-08", 2,
          "What's the name of the Linux privilege-escalation technique that abuses a "
          "scheduled task (often running as root) referencing a script or wildcard an "
          "unprivileged user can also write to?",
          ["cron job abuse", "cron jobs", "cron job exploitation"],
          ["The scheduler involved runs tasks automatically at set times or intervals.",
           "Its name is the same as the Linux daemon that runs scheduled tasks.",
           "The answer is cron job abuse."]),
        q("module-08", 3,
          "What popular enumeration script is widely used on Windows to automatically "
          "surface privilege-escalation opportunities such as misconfigured services "
          "and weak permissions?",
          "winpeas",
          ["Its name combines the OS it targets with an abbreviation for Privilege Escalation Awesome Scripts.",
           "It has a Linux sibling with a very similar name.",
           "The answer is WinPEAS."]),
        q("module-08", 4,
          "What's the Windows privilege-escalation technique called where an "
          "attacker exploits a vulnerable app that loads a malicious library file "
          "placed somewhere the app searches before the legitimate one?",
          "dll hijacking",
          ["The file type being abused is Windows' equivalent of a shared library.",
           "The attacker \"hijacks\" the load order so their malicious file gets picked up first.",
           "The answer is DLL hijacking."]),
        q("module-08", 5,
          "What Windows security feature, when bypassed, allows a program to run "
          "with administrator privileges without the normal elevation prompt appearing?",
          ["user account control", "uac"],
          ["It's the feature responsible for the \"Do you want to allow this app...\" prompt.",
           "It's commonly abbreviated to three letters.",
           "The answer is User Account Control (UAC)."]),
    ]

    # ------------------------------------------------------------------
    # Module 9 -- Pivoting y Movimiento Lateral en Redes
    # ------------------------------------------------------------------
    module_09_items = [
        q("module-09", 1,
          "What's the general term for using a compromised host as a stepping "
          "stone to reach other systems on a network segment you couldn't access directly?",
          "pivoting",
          ["It describes turning a foothold into a launching point for further access.",
           "The word describes rotating or turning around a fixed point -- your compromised host.",
           "The answer is pivoting."]),
        q("module-09", 2,
          "What SSH feature lets you forward traffic from a local port, through the "
          "SSH connection, to a destination reachable only from the remote server?",
          ["port forwarding", "ssh tunneling", "ssh port forwarding"],
          ["It's usually invoked with SSH's -L or -R command-line flags.",
           "The traffic travels through an encrypted \"tunnel\" formed by the SSH session.",
           "The answer is (SSH) port forwarding / tunneling."]),
        q("module-09", 3,
          "What type of proxy, commonly set up over an SSH connection, lets other "
          "tools route arbitrary traffic through a compromised host without a "
          "per-application tunnel?",
          ["socks proxy", "socks"],
          ["It's usually set up with SSH's -D flag for dynamic port forwarding.",
           "Tools like ProxyChains are configured to route their traffic through one of these.",
           "The answer is a SOCKS proxy."]),
        q("module-09", 4,
          "What lightweight tool is commonly used to create fast TCP/UDP tunnels "
          "over HTTP, especially useful in restrictive network environments?",
          "chisel",
          ["Its name is a hand tool used to carve a path through material.",
           "It's a single Go binary that runs both a client and a server mode.",
           "The answer is Chisel."]),
        q("module-09", 5,
          "What Linux tool is a flexible utility for relaying and redirecting "
          "traffic between sockets, often used for simple port forwarding during pivoting?",
          "socat",
          ["Its name is a blend of \"socket\" and \"cat\" (as in the Unix `cat` command).",
           "It's often described as \"netcat on steroids\" for its flexibility.",
           "The answer is socat."]),
    ]

    # ------------------------------------------------------------------
    # Module 10 -- Seguridad en IA Generativa (GenAI)
    # ------------------------------------------------------------------
    module_10_items = [
        q("module-10", 1,
          "What's the name of the attack where crafted input tricks a large "
          "language model into ignoring its original instructions and following the "
          "attacker's instead?",
          "prompt injection",
          ["It's the LLM-era analogue of classic injection vulnerabilities like SQLi.",
           "The malicious content is smuggled in through the model's own input -- its prompt.",
           "The answer is prompt injection."]),
        q("module-10", 2,
          "What's the term for an attack that tricks a model into revealing its "
          "own hidden system prompt or internal instructions?",
          ["prompt leakage", "prompt leaking"],
          ["Think of confidential information escaping somewhere it shouldn't -- a \"leak\".",
           "The target of the attack is the model's own configuration, not user data.",
           "The answer is prompt leakage."]),
        q("module-10", 3,
          "What protocol, increasingly used in agentic AI systems, standardizes "
          "how an AI model connects to and communicates with external tools and data sources?",
          ["model context protocol", "mcp"],
          ["Its acronym is three letters, starting with M.",
           "It standardizes how a model's \"context\" -- tools, data -- gets plugged in.",
           "The answer is the Model Context Protocol (MCP)."]),
        q("module-10", 4,
          "In a RAG (Retrieval-Augmented Generation) system, what's the name of the "
          "attack where an attacker inserts malicious or false content into the "
          "knowledge base the model retrieves from?",
          ["knowledge poisoning", "data poisoning", "rag poisoning"],
          ["The metaphor is the same one used for contaminating a well or water supply.",
           "It corrupts the source material the model retrieves and trusts, not the model itself.",
           "The answer is knowledge (data) poisoning."]),
        q("module-10", 5,
          "What well-known project publishes a Top 10 list of the most critical "
          "security risks specific to applications built on large language models?",
          ["owasp top 10 for llm", "owasp llm top 10", "owasp top 10 for llms"],
          ["It's produced by the same organization behind the original web-application Top 10.",
           "Its name is the familiar OWASP Top 10, applied specifically to LLM-based apps.",
           "The answer is the OWASP Top 10 for LLM Applications."]),
    ]

    # ------------------------------------------------------------------
    # Module 11 -- Repaso Final y Consolidación (broad review, spanning
    # the whole programme rather than one specific topic)
    # ------------------------------------------------------------------
    module_11_items = [
        q("module-11", 1,
          "What's the very first phase of almost every offensive security "
          "methodology, focused on gathering information before any exploitation is attempted?",
          ["reconnaissance", "recon"],
          ["It's the same phase this whole programme opened with, back in Module 3 and 5.",
           "It's often shortened to a five-letter word in casual conversation.",
           "The answer is reconnaissance (recon)."]),
        q("module-11", 2,
          "Across the OWASP Top 10, what's the general term for any vulnerability "
          "class where untrusted input is interpreted as code or commands by the "
          "receiving system (SQL, OS commands, etc.)?",
          "injection",
          ["SQL injection is the single most famous specific example of this broader category.",
           "The name describes untrusted data being \"injected\" into a place meant only for trusted code.",
           "The answer is injection."]),
        q("module-11", 3,
          "What's the general term for moving from one compromised system to "
          "another inside a network, typically after initial access and privilege escalation?",
          "lateral movement",
          ["The direction described is sideways, across a network -- not up in privilege.",
           "Pivoting (Module 9) is one of the main techniques used to achieve this.",
           "The answer is lateral movement."]),
        q("module-11", 4,
          "What's the general term for the defensive side of cybersecurity -- "
          "monitoring, detecting, and responding to attacks -- as opposed to simulating them?",
          ["blue team", "defensive security"],
          ["It's the team color associated with defense in this programme's own module naming.",
           "SIEM, threat hunting, and incident response (Module 7) all belong to this side.",
           "The answer is blue team (defensive security)."]),
        q("module-11", 5,
          "What's the general term for the offensive side of cybersecurity -- "
          "simulating real attacker techniques against a system, with permission, to "
          "find weaknesses?",
          ["red team", "offensive security"],
          ["It's the team color associated with offense in this programme's own module naming.",
           "Penetration testing is the most common specific activity under this umbrella.",
           "The answer is red team (offensive security)."]),
    ]

    all_questions = (
        module_01_items + module_02_items + module_03_items + module_04_items
        + module_05_items + module_06_items + module_07_items + module_08_items
        + module_09_items + module_10_items + module_11_items
    )

    for item in modules:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")
    for item in all_questions:
        table.put_item(Item=item)
        print(f"seeded {item['PK']} / {item['SK']}")

    print(f"\nDone -- {len(modules)} modules, {len(all_questions)} questions.")


if __name__ == "__main__":
    main()
