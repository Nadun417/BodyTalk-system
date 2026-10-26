import { describe, it, expect, afterAll } from 'vitest'
import { mkdtempSync, rmSync, readFileSync, existsSync, readdirSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { saveReportPdf, whySaveFailed } from '../src/main/services/reportService'

/**
 * Saving the report, including when saving goes wrong.
 *
 * These write real files into a temporary folder. The failures that matter are the ones a
 * person actually meets: a folder that has gone, a report that came through empty, and a file
 * already open in a PDF viewer. The last one cannot be set up portably from a test, so its
 * wording is checked directly; it was met for real in testing the installed app.
 */
const folder = mkdtempSync(join(tmpdir(), 'bodytalk-report-'))
const pdf = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37]) // "%PDF-1.7"

afterAll(() => rmSync(folder, { recursive: true, force: true }))

describe('saving the report', () => {
  it('writes exactly the bytes it was given, where it was asked to', async () => {
    const target = join(folder, 'report.pdf')
    const outcome = await saveReportPdf(pdf, target)
    expect(outcome).toEqual({ savedTo: target })
    expect(new Uint8Array(readFileSync(target))).toEqual(pdf)
  })

  it('says plainly when the folder no longer exists, and does not throw', async () => {
    const target = join(folder, 'gone', 'report.pdf')
    const outcome = await saveReportPdf(pdf, target)
    expect(outcome).toEqual({
      error: expect.stringContaining('that folder no longer exists')
    })
    expect(existsSync(join(folder, 'gone'))).toBe(false)
  })

  it('refuses a report that came through empty, and writes nothing', async () => {
    const before = readdirSync(folder).length
    const outcome = await saveReportPdf(new Uint8Array(), join(folder, 'empty.pdf'))
    expect(outcome).toEqual({ error: expect.stringContaining('empty') })
    expect(readdirSync(folder)).toHaveLength(before)
  })
})

describe('the reasons given when saving fails', () => {
  it('says a file open in another program is the problem, and what to do', () => {
    const said = whySaveFailed('EBUSY')
    expect(said).toContain('open in another program')
    expect(said).toContain('different name')
  })

  it('never passes on the system error code itself', () => {
    for (const code of [
      'EBUSY',
      'EPERM',
      'EACCES',
      'EROFS',
      'ENOENT',
      'ENOSPC',
      'EIO',
      undefined
    ]) {
      const said = whySaveFailed(code)
      expect(said).toMatch(/^The report could not be saved/)
      expect(said).not.toMatch(/E[A-Z]{3,}/)
      expect(said).not.toMatch(/resource|errno|open '/i)
    }
  })
})
