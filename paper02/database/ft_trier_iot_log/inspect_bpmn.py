"""Inspect the structure of one Camunda BPMN model from the Trier dataset."""
import sys
import xml.etree.ElementTree as ET

B = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
C = "{http://camunda.org/schema/1.0/bpmn}"

path = sys.argv[1] if len(sys.argv) > 1 else "bpmn-models/WF_101.bpmn"
root = ET.parse(path).getroot()
proc = root.find(B + "process")
print(f"process id={proc.get('id')} name={proc.get('name')}")
print()

print("== serviceTasks ==")
for st in proc.findall(B + "serviceTask"):
    print(f"  {st.get('id'):24s} name={st.get('name')}")
    for cid in st.iter(C + "connectorId"):
        print(f"      connectorId = {cid.text}")
    for ip in st.iter(C + "inputParameter"):
        txt = " ".join((ip.text or "").split())
        print(f"      in[{ip.get('name')}] = {txt[:200]}")
print()

print("== other flow nodes ==")
for tag in ("startEvent", "endEvent", "parallelGateway", "exclusiveGateway",
            "eventBasedGateway", "intermediateCatchEvent"):
    for e in proc.findall(B + tag):
        extra = ""
        med = e.find(B + "messageEventDefinition")
        if med is not None:
            extra = f"  messageRef={med.get('messageRef')}"
        print(f"  {tag:24s} {e.get('id'):24s} name={e.get('name')}{extra}")
print()

print("== sequenceFlows ==")
for sf in proc.findall(B + "sequenceFlow"):
    cond = sf.find(B + "conditionExpression")
    ctxt = f"  [{' '.join((cond.text or '').split())}]" if cond is not None else ""
    print(f"  {sf.get('sourceRef'):24s} -> {sf.get('targetRef'):24s}"
          f" name={sf.get('name')}{ctxt}")
print()

print("== messages / signals at definitions level ==")
for child in root:
    if child.tag != B + "process" and not child.tag.endswith("BPMNDiagram"):
        print(f"  {child.tag.replace(B, '')}: id={child.get('id')} name={child.get('name')}")
