import re
import glob

# Let's verify event topics referenced in 01_Production_Architecture.md exist in 11_Event_Catalog.md or 12_Event_Schemas.md
arch_file = "/home/adarsh/Documents/Youtube-Channel/PromptBook/Phase14/01_Production_Architecture.md"

with open(arch_file, "r", encoding="utf-8") as f:
    arch_text = f.read()

# Extract event names like `domain.v1.action`
arch_events = set(re.findall(r'`([a-z_]+\.v1\.[a-z_]+)`', arch_text))
print("Events referenced in Phase 14 architecture:", sorted(list(arch_events)))

event_catalog_file = "/home/adarsh/Documents/Youtube-Channel/PromptBook/11_Event_Catalog.md"
with open(event_catalog_file, "r", encoding="utf-8") as f:
    catalog_text = f.read()

catalog_events = set(re.findall(r'`([a-z_]+\.v1\.[a-z_]+)`', catalog_text))
print("Events found in 11_Event_Catalog.md:", sorted(list(catalog_events)))

missing = arch_events - catalog_events
print("\nEvents in Phase 14 not explicitly in catalog:", sorted(list(missing)))

