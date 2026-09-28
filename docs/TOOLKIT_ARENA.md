# FlyBG3Arena test field

`FlyBG3Arena` was created in BG3 Toolkit 4.1.1.6931813. It adds four crates and, after the 2026-09-24 edit, four characters to inherited level `Basic_Level_A`: a Goblin Brawler, a base Mud Mephit, and two red dragons. It is separate from the neural FlyBG3 module; it does not change the encoder, connectome, or decoder.

```text
                marker C

goblin          START          marker B

marker A                        marker D
```

Objects are `CONT_GEN_Crate_Clothing_A` instances placed by the Toolkit. The goblin uses `Goblins_Female_Guard`. Coordinates from the saved LSF files are:

| Object | Position (x, y, z) |
| --- | --- |
| Goblin Brawler | `(-3.627, 0, -2.580)` |
| Crate 000 / marker A | `(0.955, 0, -3.418)` |
| Crate 001 / marker B | `(8.272, 0, 7.577)` |
| Crate 002 / marker C | `(0.276, 0, 10.583)` |
| Crate 003 / marker D | `(5.280, 0, 0.281)` |

The crates are visual markers, not continuous walls. `Basic_Level_A` provides terrain, lighting, the start point, and navigation.

## Edit and package

1. Open BG3 Toolkit and select `FlyBG3Arena`.
2. Choose `Basic_Level_A` in Level Browser.
3. Use `Ctrl+Enter` for Game Mode and `Ctrl+Enter` again to return.
4. Save with **File → Save all** (`Ctrl+Alt+S`).
5. Close Toolkit and BG3, then run:

```powershell
.\scripts\update_arena.ps1 -DivineExe 'C:\Users\Wer\Downloads\Packed\Tools\Divine.exe'
```

The script syncs Toolkit files, builds the PAK, installs it with `-Force`, and checks SHA-256. Use `-BuildOnly` to skip installation. The separate commands are:

```powershell
.\scripts\build_arena.ps1 -DivineExe 'C:\Users\Wer\Downloads\Packed\Tools\Divine.exe'
.\scripts\install_mod.ps1 -PackageName FlyBG3Arena -Force
```

Activate both `FlyBG3Arena` and `FlyBG3` in the mod manager. Restart BG3 and test from a save made before entering the level. The Toolkit editor preview does not prove hostility, Script Extender behavior, or neural decisions in the normal game.

## Neural test

Start the bridge, then in the BG3SE server console use:

```text
Osi.TeleportPartiesToLevelWithMovie("Basic_Level_A", "FlyBG3Arena_Arrive", "")
!flybg3_spawn
!flybg3_status
!flybg3_physical on
!flybg3_combat_move on
!flybg3_observe
```

The `!` prefix is required. `brain=ready` and a fresh heartbeat are required before observing. The game ignores stale responses. The Toolkit USER MODE cannot create a new closed level in this installation; use `Basic_Level_A` for immediate tests or a separately validated level-authoring workflow.
