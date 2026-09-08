/**
 * Members showing signs of leaving, drawn as a matrix.
 *
 * Lives on the inferences screen rather than the dashboard. It answers the same
 * question the rest of this screen does — what did the calls add up to, and who
 * has to do something about it — where the dashboard answers "is anything
 * wrong" in a glance. A matrix of eight members against five warning signs is
 * not a glance.
 */

import { Link } from 'react-router-dom'

import { useMembersAtRisk } from '@/shared/api/queries'
import { maskMemberId, maskedMemberIdLabel } from '@/shared/ui/memberId'
import { Failure, Loading, Note } from '@/shared/ui/primitives'
import styles from './MembersAtRisk.module.css'

/**
 * Members showing signs of leaving, drawn as a matrix.
 *
 * Deliberately not a churn score. Nothing here has been measured against a real
 * departure, so the card names the signs each member is carrying and leaves the
 * judgement to whoever reads it — a percentage would be indistinguishable from a
 * measured one while being invented.
 *
 * A matrix rather than a list of chips because the vocabulary is small, fixed
 * and heavily repeated: as a chip per member the word "unresolved" is printed
 * once per row and reads as noise, while as a column it reads as the finding it
 * is — most of this queue is one operational problem rather than eight separate
 * member problems. The columns come from the response rather than from a list
 * here, so a factor added to the domain arrives with a column of its own; an
 * absent column would be indistinguishable from a column of no findings.
 */
export function MembersAtRisk() {
  const members = useMembersAtRisk()

  if (members.isPending) return <Loading what="members at risk" />
  if (members.error) return <Failure error={members.error} what="members at risk" />

  if (members.data.members.length === 0) {
    return <Note>No member is showing a warning sign. Shown as a result, not an omission.</Note>
  }

  const vocabulary = members.data.factor_vocabulary

  return (
    <>
      <div className={styles.matrixScroll}>
        <table className={styles.matrix} aria-label="Members showing warning signs">
          <thead>
            <tr>
              <th scope="col">Member</th>
              {vocabulary.map((factor) => (
                // The full sentence is the accessible name and the tooltip; the
                // heading itself has a column's worth of room and no more.
                <th key={factor.code} scope="col">
                  <abbr title={factor.label}>{factor.short_label}</abbr>
                </th>
              ))}
              <th scope="col">Score</th>
            </tr>
          </thead>
          <tbody>
            {members.data.members.map((member) => (
              <tr key={member.member_id}>
                <th scope="row">
                  {/* Filtered by member, not searched by reference: a search
                      finds one call, and the point of this row is all of them. */}
                  <Link to={`/calls?member=${encodeURIComponent(member.member_id)}`}>
                    {member.member_name ? (
                      <>
                        {member.member_name}{' '}
                        {/* Kept beside the name rather than dropped: two members
                            can share a name, and the last four characters are
                            what tells them apart. */}
                        <span
                          className={styles.memberId}
                          title={maskedMemberIdLabel(member.member_id)}
                        >
                          ({maskMemberId(member.member_id)})
                        </span>
                      </>
                    ) : (
                      // No call of theirs stated a name. The identifier alone is
                      // still true; a placeholder like "Unknown" would not be.
                      <span title={maskedMemberIdLabel(member.member_id)}>
                        {maskMemberId(member.member_id)}
                      </span>
                    )}
                  </Link>
                  <span className={styles.matrixCalls}>
                    {member.call_count === 1 ? '1 call' : `${String(member.call_count)} calls`}
                  </span>
                </th>
                {vocabulary.map((factor) => {
                  const shown = member.factors.includes(factor.code)
                  return (
                    <td key={factor.code}>
                      {/* The mark carries no text, so the cell states in words
                          what it means. Colour and a filled square are not
                          readable by everyone, and this is the whole content of
                          the row. */}
                      <span className={shown ? styles.markOn : styles.markOff} aria-hidden="true" />
                      <span className={styles.visuallyHidden}>
                        {shown ? factor.label : `Not ${factor.label.toLowerCase()}`}
                      </span>
                    </td>
                  )
                })}
                {/* The worst call this member had, which is what separates two
                    members showing the same signs and was previously fetched
                    and never drawn. */}
                <td className={styles.matrixScore}>{member.lowest_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
