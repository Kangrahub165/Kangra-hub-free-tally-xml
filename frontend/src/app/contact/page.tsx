'use client';

import React, { useState } from 'react';
import { Send, CheckCircle2, MessageSquare, AlertCircle, HelpCircle, Mail, Building2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

import { submitPublicContact } from '@/lib/api';

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [referenceId, setReferenceId] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subjectType: 'REPORT_ISSUE',
    jobId: '',
    bankName: '',
    message: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await submitPublicContact({
        name: formData.name.trim(),
        email: formData.email.trim(),
        subject_type: formData.subjectType,
        job_id: formData.jobId.trim() || undefined,
        bank_name: formData.bankName.trim() || undefined,
        message: formData.message.trim(),
      });
      setReferenceId(res.reference_id);
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Failed to submit message. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="py-16 bg-slate-50 min-h-screen">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <Badge variant="primary" size="sm" className="mb-3">
            Support & Inquiries
          </Badge>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Contact Kangra Hub Support
          </h1>
          <p className="mt-3 text-sm text-slate-600 leading-relaxed">
            Have a statement formatting question, format request, or issue with a converted file? Our engineering team is here to assist.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Guidelines & Channels (4 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <Card className="p-6">
              <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-brand-600" /> Reporting Guidelines
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed mb-4">
                To help us troubleshoot statement conversion mismatches rapidly, please provide:
              </p>
              <ul className="space-y-2 text-xs text-slate-700">
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-600 flex-shrink-0 mt-1.5" />
                  <span>The <strong>Reference ID</strong> shown during failed conversions.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-600 flex-shrink-0 mt-1.5" />
                  <span>The bank name and account statement type.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-600 flex-shrink-0 mt-1.5" />
                  <span>Do not send sensitive passwords or raw banking credentials.</span>
                </li>
              </ul>
            </Card>

            <Card className="p-6 bg-slate-900 text-white border-slate-800">
              <h3 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-brand-400" /> Request New Bank Parser
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed mb-3">
                Need support for a cooperative bank or regional rural bank (RRB)? Select "Suggest a New Bank Statement Format" to submit statement headers for parser integration.
              </p>
              <span className="text-[11px] font-semibold text-brand-300">
                Typical parser integration turn-around: 24–48 hours.
              </span>
            </Card>
          </div>

          {/* Right Column: Contact Form (7 cols) */}
          <div className="lg:col-span-7">
            <Card className="p-7 sm:p-8 shadow-card">
              {submitted ? (
                <div className="text-center py-12 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h2 className="text-lg font-bold text-slate-900">Message Received</h2>
                    <p className="text-xs text-slate-600 max-w-sm mx-auto leading-relaxed">
                      Thank you for reaching out. We have logged your request and dispatched it to our support specialists.
                    </p>
                  </div>
                  {referenceId && (
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl max-w-xs mx-auto text-xs text-slate-600">
                      Tracking Reference: <strong className="font-mono text-slate-900">{referenceId}</strong>
                    </div>
                  )}
                  <div className="pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSubmitted(false);
                        setFormData({
                          name: '',
                          email: '',
                          subjectType: 'REPORT_ISSUE',
                          jobId: '',
                          bankName: '',
                          message: '',
                        });
                      }}
                    >
                      Send Another Inquiry
                    </Button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  {error && (
                    <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 font-medium flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  <Input
                    label="Your Full Name"
                    required
                    placeholder="e.g. Anil Kumar"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />

                  <Input
                    label="Email Address"
                    type="email"
                    required
                    placeholder="e.g. anil@example.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />

                  <Select
                    label="Inquiry Type"
                    value={formData.subjectType}
                    onChange={(e) => setFormData({ ...formData, subjectType: e.target.value })}
                  >
                    <option value="REPORT_ISSUE">Report a Conversion Issue / Math Mismatch</option>
                    <option value="SUGGEST_BANK">Suggest a New Bank Statement Format</option>
                    <option value="UNLIMITED_INQUIRY">Request Unlimited Quota (CA Firms & Enterprise)</option>
                    <option value="GENERAL">General Feedback / Inquiries</option>
                  </Select>

                  {formData.subjectType === 'REPORT_ISSUE' && (
                    <Input
                      label="Reference ID / Job ID (Optional)"
                      placeholder="e.g. KH-9F2B81"
                      value={formData.jobId}
                      onChange={(e) => setFormData({ ...formData, jobId: e.target.value })}
                      helperText="Quote the reference code from the error message for instant log lookup."
                    />
                  )}

                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      Message Details
                    </label>
                    <textarea
                      rows={4}
                      required
                      placeholder="Describe the issue, bank name, or details..."
                      value={formData.message}
                      onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                      className="w-full bg-white text-sm text-slate-900 rounded-xl border border-slate-300 p-3.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-600 transition-all placeholder:text-slate-400"
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    className="w-full mt-2"
                    loading={loading}
                    iconRight={<Send className="w-4 h-4" />}
                  >
                    Submit Support Request
                  </Button>
                </form>
              )}
            </Card>
          </div>

        </div>

      </div>
    </div>
  );
}
