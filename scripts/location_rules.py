"""Conservative, evidence-based work-location gate; scores cannot override it."""
import re

POLICY_VERSION = "taipei-taiwan-remote-v1"


def match(pattern, text):
    return re.search(pattern, text, re.I)


def classify_location(location, description="", workplace=""):
    location = location or ""
    description = description or ""
    label = f"{location} {workplace}"
    # A company mentioning Taipei in its biography is not a Taipei vacancy.
    taipei = bool(match(r"\btaipei\b|台北|臺北", re.sub(
        r"new\s+taipei|新北|greater\s+taipei|大台北|大臺北", "", location, flags=re.I)))
    remote = bool(match(r"\bremote\b|home[- ]based|遠端|遠程", label) or match(
        r"(?:this|the) (?:role|position|job) is (?:fully |100% |globally )?remote|"
        r"work from anywhere|fully remote (?:role|position)|本職位.*全遠端", description))
    negative = bool(match(r"not (?:a )?remote|no remote|不提供遠端|不可遠端", label + " " + description))
    hybrid = bool(match(r"hybrid|on[- ]site|混合|駐點", label))
    evidence = [f"招募地點：{location or '未提供'}"]
    if workplace:
        evidence.append(f"工作模式：{workplace}")

    def result(disposition, key, reason):
        return {"locationPolicy": POLICY_VERSION, "locationDisposition": disposition,
                "locationKey": key, "locationReason": reason,
                "locationEvidence": evidence, "rawLocation": location,
                "workplaceType": workplace}

    if taipei:
        return result("eligible", "taipei", "招募地點明列台北；實體或混合辦公皆納入")
    if not remote or negative or hybrid:
        return result("excluded", "outside", "非台北實體／混合辦公，且未明示可全遠端工作")

    sentences = re.split(r"(?<=[.!?。;])\s+|\n+", description)
    relevant = [s.strip() for s in sentences if match(
        r"remote|resid|based in|work authori|right to work|travel|in.person|on.site|遠端|居住|出差", s)]
    evidence.extend(s[:500] for s in relevant[:6])
    if match(r"(?:except|excluding|not available in|cannot hire in|not eligible in).{0,40}(?:taiwan|台灣|臺灣)|"
             r"不接受.{0,10}(?:台灣|臺灣)", description):
        return result("excluded", "outside", "職缺明示不接受台灣工作者")
    # Region restrictions and attendance requirements take precedence over 'remote'.
    restriction = match(
        r"(?:must|need to|required to|only)\s+(?:be |currently )?(?:based|reside|located|live)\s+in\s+([^.;\n]+)|"
        r"(?:authorized|authorised|eligible|right|authorization)\s+to work in\s+([^.;\n]+)|"
        r"remote\s+(?:only\s+)?(?:within|from|in)\s+([^.;\n]+)|"
        r"(?:can only hire|can only employ|eligible countries|candidates must reside)\s*(?:in|:)\s*([^.;\n]+)|"
        r"(?:US|U\.S\.|USA|UK|United States|United Kingdom|Canada|Europe|EMEA|Singapore)[ -]+only\b", description)
    if restriction:
        clause = restriction.group(0)
        evidence.append(clause[:500])
        if not match(r"taiwan|台灣|臺灣|anywhere|worldwide", clause):
            return result("excluded", "outside", "職缺要求居住／工作授權於其他地區，不能直接視為可從台灣遠端")
    if match(r"(?:required|must|expected|ability|willing|willingness).{0,65}(?:travel|in.person|on.site)|"
             r"(?:travel|in.person|on.site|in the office).{0,65}(?:required|mandatory|twice|annually|per year|yearly|per week)|"
             r"必須.{0,30}(?:出差|到場)|定期.{0,20}(?:出差|實體)", description):
        return result("excluded", "outside", "包含必須到場／出差的要求，不符合國際工作只能線上的偏好")

    # Only job-location fields or role-specific statements establish worldwide scope.
    worldwide = bool(match(r"worldwide|anywhere|global|全球", location) or match(
        r"work from anywhere|(?:role|position|job) is (?:fully )?globally remote|"
        r"(?:role|position|job).{0,35}remote.{0,25}worldwide", description))
    taiwan = bool(match(r"taiwan|台灣|臺灣", location) or match(
        r"remote.{0,30}(?:from|in) taiwan|可.{0,10}(?:台灣|臺灣).{0,10}遠端", description))
    # 'Remote - Singapore', 'US/Canada Remote', 'EMEA' etc are not worldwide.
    generic = re.sub(r"remote|home[- ]based|apac|asia[- ]pacific|asia|全球|遠端|[\s,;/()\-–]+", "", location, flags=re.I)
    if not worldwide and not taiwan and generic:
        return result("excluded", "outside", "遠端地點限定其他地區，未明示接受台灣工作者")
    if worldwide or taiwan:
        return result("eligible", "remote", "職缺明列台灣或全球全遠端；仍需確認聘僱、時區與學籍資格")
    return result("review", "remote-review", "職缺明示遠端，但未確認接受台灣工作者；暫不列入目前機會")


def classify_saved_job(job):
    if job.get("locationPolicy") == POLICY_VERSION:
        return {k: job[k] for k in ("locationPolicy", "locationDisposition", "locationKey",
                "locationReason", "locationEvidence", "rawLocation", "workplaceType")}
    return classify_location(job.get("rawLocation", job.get("location", "")),
                             " ".join(job.get(k, "") for k in ("timing", "eligibility", "risk")),
                             job.get("workplaceType", ""))
