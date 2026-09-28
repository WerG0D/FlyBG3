# Flyman Mud Mephit body

Flyman is a mod-owned root template derived from `MEPHIT_Mud_A`. Its `MapKey` identifies a mod resource, not a save instance; `CreateAtObject` supplies the real UUID. The encoder, MaleCNS, and motor decoder are unchanged. The server adapter creates Flyman near the host and requests `AddPartyFollower(Flyman, host)`.

## Test procedure

1. Close BG3 and build/install the package.
2. Start the Python bridge in a separate terminal.
3. Load a separate save and open the BG3SE server console outside combat.
4. Run `!flybg3_spawn`, then `!flybg3_status`.
5. Confirm `follower=1`, `brain=ready`, and a fresh heartbeat before `!flybg3_observe`.

```text
!flybg3_spawn
!flybg3_status
!flybg3_physical on
!flybg3_combat_move on
!flybg3_observe
```

`MakePlayer` did not provide player control for the tested Mud Mephit save. The follower route did provide a controllable turn and is the supported route. The adapter refuses to observe or act unless `IsPartyFollower` or `IsPlayer` confirms control. It never replaces the avatar or accepts an unverified UUID.

If the bridge is absent, BG3 may print `Observation #N sent` followed by a timeout. If `hostile=0`, `in_range=0`, or `visible=0` appears in the sensory scan, the adapter has no current stimulus and will not invent one. `ImmortalForTesting=true` applies `SetImmortal` only after verifying Flyman's template; it does not resurrect a dead creature.

The instance UUID is stored in the Script Extender `settings.json`. Re-running `!flybg3_spawn` recovers the existing Flyman before creating another. Use a separate save for testing.
