from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import User, Team, TeamMember, Competitor
from pydantic import BaseModel
from typing import Optional
import traceback

router = APIRouter(prefix="/teams", tags=["teams"])


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class InviteMember(BaseModel):
    email: str
    role: Optional[str] = "member"


@router.get("/")
async def list_teams(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        memberships = await db.execute(
            select(TeamMember).where(TeamMember.user_id == uid)
        )
        members = memberships.scalars().all()
        teams = []
        for m in members:
            team_result = await db.execute(
                select(Team).where(Team.id == m.team_id)
            )
            team = team_result.scalar_one_or_none()
            if not team:
                continue
            members_result = await db.execute(
                select(TeamMember).where(TeamMember.team_id == team.id)
            )
            team_members = members_result.scalars().all()
            member_list = []
            for tm in team_members:
                user_result = await db.execute(
                    select(User).where(User.id == tm.user_id)
                )
                u = user_result.scalar_one_or_none()
                if u:
                    member_list.append({
                        "id": tm.id,
                        "user_id": u.id,
                        "email": u.email,
                        "name": u.name or u.email,
                        "role": tm.role,
                        "joined_at": tm.joined_at.isoformat() if tm.joined_at else None
                    })
            comp_result = await db.execute(
                select(Competitor).where(Competitor.team_id == team.id)
            )
            shared_comps = comp_result.scalars().all()
            teams.append({
                "id": team.id,
                "name": team.name,
                "description": team.description or "",
                "owner_id": team.owner_id,
                "is_owner": team.owner_id == uid,
                "my_role": m.role,
                "member_count": len(member_list),
                "members": member_list,
                "shared_competitors": len(shared_comps),
                "created_at": team.created_at.isoformat() if team.created_at else None
            })
        return teams
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Teams List Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.post("/")
async def create_team(data: TeamCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        team = Team(name=data.name, description=data.description or "", owner_id=uid)
        db.add(team)
        await db.flush()
        member = TeamMember(team_id=team.id, user_id=uid, role="owner")
        db.add(member)
        await db.commit()
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "message": f"Team '{team.name}' created!"
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Team Create Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.post("/{team_id}/invite")
async def invite_member(team_id: int, data: InviteMember, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        team_result = await db.execute(select(Team).where(Team.id == team_id))
        team = team_result.scalar_one_or_none()
        if not team:
            raise HTTPException(404, "Team not found")
        my_member = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == uid)
        )
        me = my_member.scalar_one_or_none()
        if not me or me.role not in ("owner", "admin"):
            raise HTTPException(403, "Only owners and admins can invite members")
        user_result = await db.execute(
            select(User).where(User.email == data.email.strip().lower())
        )
        target_user = user_result.scalar_one_or_none()
        if not target_user:
            raise HTTPException(404, f"No user found with email {data.email}. They need to sign up first.")
        existing = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == target_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"{data.email} is already a team member")
        new_member = TeamMember(team_id=team_id, user_id=target_user.id, role=data.role or "member")
        db.add(new_member)
        await db.commit()
        return {
            "message": f"Invited {data.email} as {data.role or 'member'}",
            "user_id": target_user.id,
            "email": target_user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Invite Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.delete("/{team_id}/members/{member_id}")
async def remove_member(team_id: int, member_id: int, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        my_member = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == uid)
        )
        me = my_member.scalar_one_or_none()
        if not me or me.role not in ("owner", "admin"):
            raise HTTPException(403, "Only owners and admins can remove members")
        target = await db.execute(
            select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team_id)
        )
        tm = target.scalar_one_or_none()
        if not tm:
            raise HTTPException(404, "Member not found")
        if tm.role == "owner":
            raise HTTPException(400, "Cannot remove the team owner")
        await db.delete(tm)
        await db.commit()
        return {"message": "Member removed"}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Remove Member Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.post("/{team_id}/share/{competitor_id}")
async def share_competitor(team_id: int, competitor_id: int, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        my_member = await db.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == uid)
        )
        if not my_member.scalar_one_or_none():
            raise HTTPException(403, "Not a team member")
        comp_result = await db.execute(
            select(Competitor).where(Competitor.id == competitor_id, Competitor.user_id == uid)
        )
        comp = comp_result.scalar_one_or_none()
        if not comp:
            raise HTTPException(404, "Competitor not found")
        comp.team_id = team_id
        await db.commit()
        return {"message": f"Shared {comp.name} with team"}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Share Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.post("/{team_id}/unshare/{competitor_id}")
async def unshare_competitor(team_id: int, competitor_id: int, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        comp_result = await db.execute(
            select(Competitor).where(Competitor.id == competitor_id, Competitor.user_id == uid, Competitor.team_id == team_id)
        )
        comp = comp_result.scalar_one_or_none()
        if not comp:
            raise HTTPException(404, "Competitor not found in this team")
        comp.team_id = None
        await db.commit()
        return {"message": f"Unshared {comp.name} from team"}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Unshare Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})


@router.delete("/{team_id}")
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        uid = current_user["user_id"]
        team_result = await db.execute(select(Team).where(Team.id == team_id))
        team = team_result.scalar_one_or_none()
        if not team:
            raise HTTPException(404, "Team not found")
        if team.owner_id != uid:
            raise HTTPException(403, "Only the owner can delete the team")
        comps = await db.execute(
            select(Competitor).where(Competitor.team_id == team_id)
        )
        for c in comps.scalars().all():
            c.team_id = None
        await db.delete(team)
        await db.commit()
        return {"message": f"Team '{team.name}' deleted"}
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Delete Team Error] {e}\n{tb}")
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})