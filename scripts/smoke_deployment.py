"""HTTP smoke test for an isolated deployment, with an explicit opt-in write."""
import argparse
import json
import uuid
from datetime import date, timedelta
from pathlib import Path
import httpx

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--write-booking", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("runtime/deployment-smoke.json"))
    parser.add_argument("--verify-report", type=Path)
    args=parser.parse_args()
    with httpx.Client(base_url=args.base_url,timeout=200,trust_env=False) as client:
        for path in ("/api/live","/api/ready","/api/health","/api/profile","/api/catalog","/api/bookings","/api/observability","/"):
            result=client.get(path)
            result.raise_for_status()
        if args.verify_report:
            report=json.loads(args.verify_report.read_text(encoding="utf-8"))
            assert any(b["booking_id"]==report["booking_id"] for b in client.get("/api/bookings").json())
            assert client.get("/api/observability").json()["summary"]["requests"] >= report["traced_requests"]
            print("Restart persistence verified for booking and activity.")
            return
        if args.write_booking:
            before=client.get("/api/bookings").json()
            day=str(date.today()+timedelta(days=365))
            body={"session_id":"deployment-"+uuid.uuid4().hex,"request_id":uuid.uuid4().hex,
                  "message":"Book D101 T001 "+day+" 10:00"}
            result=client.post("/api/chat",json=body)
            result.raise_for_status()
            data=result.json()
            assert data["booking"], "No booking was created"
            after=client.get("/api/bookings").json()
            assert len(after)==len(before)+1 and any(b["booking_id"]==data["booking"]["booking_id"] for b in after)
            assert client.post("/api/chat",json=body).json()==data
            assert client.get("/api/bookings").json()==after
            report={"booking_id":data["booking"]["booking_id"],
                    "traced_requests":client.get("/api/observability").json()["summary"]["requests"]}
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
        print("HTTP smoke passed. Booking writes: "+str(args.write_booking))

if __name__=="__main__":
    main()
